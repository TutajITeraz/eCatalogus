#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_ENV="${SCRIPT_DIR}/config/example.env"

INSTALL_UNIT=0
DRY_RUN=0
NON_INTERACTIVE=0
EDIT_CONFIG=0
FORCE_RESET=0
CFG_ARG=""
CONFIG_SOURCE=""
ACTION=""
CONFIG_WAS_PROVIDED=0
LOG_FILE=""
GAUGE_PID=""
GAUGE_PIPE=""
TMP_PRESERVE=""
PYTHON_BIN=""
ENV_FILE=""
SYSTEM_PYTHON_BIN=""
MEDIA_DIR=""
DB_CHARSET="utf8mb4"
DB_COLLATION="utf8mb4_unicode_ci"

usage() {
  cat <<EOF
Usage: $(basename "$0") [config.env] [--install-unit] [--dry-run] [--action full|env|venv] [--non-interactive] [--edit-config] [--force-reset]

Options:
  --install-unit     Install and enable generated systemd unit (requires root or sudo)
  --dry-run          Show actions without making changes
  --action VALUE     Action to run: full, env, or venv
  --non-interactive  Do not show menus or prompts; requires a complete config file
  --edit-config      Re-open interactive config editing even when a config file is provided
  --force-reset      Discard unpreserved local git changes before updating from origin
  -h, --help         Show this help
EOF
}

timestamp() { date +%Y%m%d-%H%M%S; }
log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
warn() { log "WARNING: $*"; }
die() { log "ERROR: $*"; exit 1; }

upsert_env_value() {
  local file=$1
  local key=$2
  local value=$3
  local tmp

  tmp=$(mktemp)
  if [[ -f "$file" ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { updated = 0 }
      $0 ~ "^" key "=" {
        print key "=" value
        updated = 1
        next
      }
      { print }
      END {
        if (!updated) {
          print key "=" value
        }
      }
    ' "$file" > "$tmp"
  else
    printf '%s=%s\n' "$key" "$value" > "$tmp"
  fi

  mv "$tmp" "$file"
}

sanitize() {
  # Remove CR and LF characters which may be present when reading from prompts
  local v=${1-}
  v="${v//$'\r'/}"
  v="${v//$'\n'/}"
  printf '%s' "$v"
}

cleanup() {
  stop_gauge
  if [[ -n "$TMP_PRESERVE" && -d "$TMP_PRESERVE" ]]; then
    rm -rf "$TMP_PRESERVE"
  fi
}

trap cleanup EXIT

parse_args() {
  while (($#)); do
    case "$1" in
      --install-unit)
        INSTALL_UNIT=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --non-interactive)
        NON_INTERACTIVE=1
        shift
        ;;
      --edit-config)
        EDIT_CONFIG=1
        shift
        ;;
      --force-reset)
        FORCE_RESET=1
        shift
        ;;
      --action)
        [[ $# -ge 2 ]] || die "--action requires a value"
        ACTION="$2"
        shift 2
        ;;
      --action=*)
        ACTION="${1#*=}"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --*)
        die "Unknown option: $1"
        ;;
      *)
        if [[ -z "$CFG_ARG" ]]; then
          CFG_ARG="$1"
          CONFIG_WAS_PROVIDED=1
          shift
        else
          die "Unexpected extra argument: $1"
        fi
        ;;
    esac
  done
}

whiptail_ok() {
  # Only use whiptail when available and when stdout is a terminal
  command -v whiptail >/dev/null 2>&1 && [[ "$NON_INTERACTIVE" -eq 0 ]] && [[ -t 1 ]]
}

restore_tty() {
  stty sane 2>/dev/null || true
  tput reset 2>/dev/null || true
  sleep 0.02
}

start_gauge() {
  if whiptail_ok; then
    GAUGE_PIPE=$(mktemp -u)
    mkfifo "$GAUGE_PIPE"
    whiptail --title "Installer" --gauge "Starting..." 8 70 0 < "$GAUGE_PIPE" &
    GAUGE_PID=$!
    exec 3> "$GAUGE_PIPE"
  fi
}

update_gauge() {
  local pct=$1
  local msg=${2-}
  if [[ -n "$GAUGE_PID" ]]; then
    echo "$pct" >&3
    echo "$msg" >&3
  else
    log "PROGRESS: ${pct}% - ${msg}"
  fi
}

stop_gauge() {
  if [[ -n "$GAUGE_PID" ]]; then
    exec 3>&- || true
    wait "$GAUGE_PID" 2>/dev/null || true
    rm -f "$GAUGE_PIPE" 2>/dev/null || true
    GAUGE_PID=""
    GAUGE_PIPE=""
  fi
}

ask() {
  local prompt=$1
  local default=${2-}
  if whiptail_ok; then
    local out
    out=$(whiptail --title "Installer" --inputbox "$prompt" 10 70 "$default" 3>&1 1>&2 2>&3) || return 1
    restore_tty
    printf '%s\n' "$out"
  elif [[ "$NON_INTERACTIVE" -eq 1 ]]; then
    [[ -n "$default" ]] || return 1
    printf '%s\n' "$default"
  else
    local ans
    read -rp "$prompt [${default}]: " ans </dev/tty || return 1
    printf '%s\n' "${ans:-$default}"
  fi
}

ask_secret() {
  local prompt=$1
  local default=${2-}
  if whiptail_ok; then
    local out
    out=$(whiptail --title "Installer" --passwordbox "$prompt" 10 70 3>&1 1>&2 2>&3) || return 1
    restore_tty
    printf '%s\n' "${out:-$default}"
  elif [[ "$NON_INTERACTIVE" -eq 1 ]]; then
    [[ -n "$default" ]] || return 1
    printf '%s\n' "$default"
  else
    local ans
    read -rsp "$prompt: " ans </dev/tty || return 1
    echo
    printf '%s\n' "${ans:-$default}"
  fi
}

confirm() {
  local prompt=$1
  if whiptail_ok; then
    if whiptail --title "Installer" --yesno "$prompt" 10 70; then
      restore_tty
      return 0
    fi
    restore_tty
    return 1
  fi

  if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
    return 1
  fi

  local yn
  read -rp "$prompt [y/N]: " yn </dev/tty || return 1
  [[ "$yn" =~ ^[Yy]$ ]]
}

show_main_menu() {
  if [[ -n "$ACTION" ]]; then
    ACTION_SELECTED="$ACTION"
    return 0
  fi

  if whiptail_ok; then
    local choice
    choice=$(whiptail --title "Installer" --menu "Choose action" 15 70 4 \
      "full" "Full install or update" \
      "env" "Create or update APPDIR/.env" \
      "venv" "Create virtualenv only" \
      "quit" "Quit" 3>&1 1>&2 2>&3) || return 1
    restore_tty
    ACTION_SELECTED="$choice"
  else
    ACTION_SELECTED="full"
  fi
}

show_config_form() {
  if ! whiptail_ok; then
    return 1
  fi

  local form_arr=()
  local status=0
  mapfile -t form_arr < <(
    whiptail --title "Instance configuration" --form "Edit fields (TAB to move)" 20 90 12 \
      "Domain" 1 1 "${DOMAIN}" 1 30 55 0 \
      "Deploy user" 2 1 "${DEPLOY_USER}" 2 30 55 0 \
      "Repository URL" 3 1 "${REPO_URL}" 3 30 55 0 \
      "Git branch" 4 1 "${GIT_BRANCH}" 4 30 55 0 \
      "App dir" 5 1 "${APPDIR}" 5 30 55 0 \
      "Venv path" 6 1 "${VENV_PATH}" 6 30 55 0 \
      "Service shortname" 7 1 "${SERVICE_SHORTNAME}" 7 30 55 0 \
      "Use TCP (0/1)" 8 1 "${USE_TCP}" 8 30 55 0 \
      "Port" 9 1 "${PORT}" 9 30 55 0 \
      "Socket path" 10 1 "${SOCKET_PATH}" 10 30 55 0 \
      "Preserve files (comma)" 11 1 "${PRESERVE_FILES}" 11 30 55 0 3>&1 1>&2 2>&3
  ) || status=$?
  restore_tty
  [[ "$status" -eq 0 ]] || return 1
  if [[ "${#form_arr[@]}" -ne 11 ]]; then
    warn "Configuration form returned ${#form_arr[@]} fields; expected 11. Falling back to sequential prompts."
    return 1
  fi

  DOMAIN=${form_arr[0]}
  DEPLOY_USER=${form_arr[1]}
  REPO_URL=${form_arr[2]}
  GIT_BRANCH=${form_arr[3]}
  APPDIR=${form_arr[4]}
  VENV_PATH=${form_arr[5]}
  SERVICE_SHORTNAME=${form_arr[6]}
  USE_TCP=${form_arr[7]}
  PORT=${form_arr[8]}
  SOCKET_PATH=${form_arr[9]}
  PRESERVE_FILES=${form_arr[10]}
}

load_config() {
  local candidate=""
  if [[ -n "$CFG_ARG" ]]; then
    candidate="$CFG_ARG"
  else
    candidate="$DEFAULT_ENV"
  fi

  [[ -f "$candidate" ]] || die "Config file not found: $candidate"
  CONFIG_SOURCE="$candidate"
  # shellcheck source=/dev/null
  source "$candidate"
}

expand_template_value() {
  local value=${1-}
  eval "printf '%s' \"$value\""
}

canonical_repo_url() {
  local url=$1
  url=${url%.git}
  printf '%s\n' "$url"
}

normalize_repo_url() {
  if [[ "$REPO_URL" =~ ^https://github.com/[^[:space:]]+$ && "$REPO_URL" != *.git ]]; then
    REPO_URL="${REPO_URL}.git"
  fi
}

resolve_config() {
  DOMAIN=${DOMAIN:-}
  DEPLOY_USER=${DEPLOY_USER:-}
  REPO_URL=${REPO_URL:-}
  GIT_BRANCH=${GIT_BRANCH:-main}
  SERVICE_SHORTNAME=${SERVICE_SHORTNAME:-}
  USE_TCP=${USE_TCP:-0}
  PORT=${PORT:-}
  SOCKET_PATH=${SOCKET_PATH:-}
  PRESERVE_FILES=${PRESERVE_FILES:-}
  PYTHON_BIN=${PYTHON_BIN:-}
  TCP_BIND_HOST=${TCP_BIND_HOST:-127.0.0.1}

  APPDIR=${APPDIR:-/home/${DEPLOY_USER}/domains/${DOMAIN}/ecatalogus}
  VENV_PATH=${VENV_PATH:-${APPDIR}/.venv}
  STATIC_DIR=${STATIC_DIR:-${APPDIR}/static_assets}
  PUBLIC_HTML=${PUBLIC_HTML:-/home/${DEPLOY_USER}/domains/${DOMAIN}/public_html}
  LOG_DIR=${LOG_DIR:-${APPDIR}/logs}
  DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-ecatalogus.settings}
  MEDIA_DIR=${MEDIA_DIR:-}

  normalize_repo_url

  APPDIR=$(expand_template_value "$APPDIR")
  VENV_PATH=$(expand_template_value "$VENV_PATH")
  STATIC_DIR=$(expand_template_value "$STATIC_DIR")
  PUBLIC_HTML=$(expand_template_value "$PUBLIC_HTML")
  LOG_DIR=$(expand_template_value "$LOG_DIR")
  SOCKET_PATH=$(expand_template_value "$SOCKET_PATH")
  if [[ -n "$MEDIA_DIR" ]]; then
    MEDIA_DIR=$(expand_template_value "$MEDIA_DIR")
  fi
}

resolve_instance_runtime_paths() {
  if [[ -n "$MEDIA_DIR" ]]; then
    return 0
  fi

  local module_name="${DJANGO_SETTINGS_MODULE##*.}"
  if [[ "$module_name" == settings_* ]]; then
    MEDIA_DIR="${APPDIR}/media_instances/${module_name#settings_}"
    return 0
  fi

  MEDIA_DIR="${APPDIR}/media"
}

validate_required() {
  local missing=()
  local name
  for name in DOMAIN DEPLOY_USER REPO_URL GIT_BRANCH APPDIR VENV_PATH SERVICE_SHORTNAME PUBLIC_HTML LOG_DIR DJANGO_SETTINGS_MODULE; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
  done
  if ((${#missing[@]})); then
    die "Missing required config values: ${missing[*]}"
  fi

  [[ "$USE_TCP" =~ ^[01]$ ]] || die "USE_TCP must be 0 or 1"
  [[ "$APPDIR" = /* ]] || die "APPDIR must be an absolute path"
  [[ "$VENV_PATH" = /* ]] || die "VENV_PATH must be an absolute path"
  [[ "$PUBLIC_HTML" = /* ]] || die "PUBLIC_HTML must be an absolute path"
  [[ "$LOG_DIR" = /* ]] || die "LOG_DIR must be an absolute path"
  [[ "$STATIC_DIR" = /* ]] || die "STATIC_DIR must be an absolute path"
  [[ "$SERVICE_SHORTNAME" =~ ^[A-Za-z0-9_.-]+$ ]] || die "SERVICE_SHORTNAME contains unsupported characters"

  if [[ "$USE_TCP" -eq 1 ]]; then
    [[ -n "$PORT" ]] || die "PORT is required when USE_TCP=1"
    [[ "$PORT" =~ ^[0-9]+$ ]] || die "PORT must be numeric"
    ((PORT >= 1 && PORT <= 65535)) || die "PORT must be between 1 and 65535"
  else
    [[ -n "$SOCKET_PATH" ]] || die "SOCKET_PATH is required when USE_TCP=0"
    [[ "$SOCKET_PATH" = /* ]] || die "SOCKET_PATH must be an absolute path"
  fi
}

ensure_required_commands() {
  local cmd
  for cmd in git sed awk cp mv mkdir ln tee; do
    command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: $cmd"
  done
}

select_system_python() {
  local candidate
  if [[ -n "$PYTHON_BIN" ]]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Configured PYTHON_BIN not found: $PYTHON_BIN"
    SYSTEM_PYTHON_BIN=$PYTHON_BIN
    return 0
  fi
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      SYSTEM_PYTHON_BIN=$candidate
      return 0
    fi
  done
  die "No suitable Python interpreter found. Set PYTHON_BIN in the config file."
}

is_port_free() {
  local port=$1
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$port" | grep -q LISTEN && return 1 || return 0
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 1 || return 0
  else
    warn "Neither ss nor lsof is available; skipping port availability check"
    return 0
  fi
}

ensure_ssh_known_host() {
  local repo_host=${1:-github.com}
  local ssh_dir="${HOME}/.ssh"
  local known_hosts="${ssh_dir}/known_hosts"
  mkdir -p "$ssh_dir"
  chmod 700 "$ssh_dir" || true
  if command -v ssh-keyscan >/dev/null 2>&1; then
    if ! grep -q "^${repo_host}[ ,]" "$known_hosts" 2>/dev/null; then
      if [[ "$DRY_RUN" -eq 1 ]]; then
        log "DRY-RUN: would add SSH host key for ${repo_host}"
      else
        ssh-keyscan -t rsa,ecdsa,ed25519 "$repo_host" >> "$known_hosts" 2>/dev/null || true
        chmod 644 "$known_hosts" || true
      fi
    fi
  fi
}

ensure_ssh_key() {
  local repo=$1
  local ssh_dir="${HOME}/.ssh"
  if [[ ! "$repo" =~ ^git@ ]]; then
    return 0
  fi
  if [[ -f "${ssh_dir}/id_ed25519" || -f "${ssh_dir}/id_rsa" ]]; then
    return 0
  fi
  confirm "No SSH key found in ${ssh_dir}. Generate one now?" || die "SSH repository requires a deploy key, and none is available."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would generate SSH key in ${ssh_dir}"
    return 0
  fi
  mkdir -p "$ssh_dir"
  chmod 700 "$ssh_dir"
  ssh-keygen -t ed25519 -f "${ssh_dir}/id_ed25519" -N "" -C "deploy@$(hostname)"
  chmod 600 "${ssh_dir}/id_ed25519" || true
  log "Generated SSH key. Add this public key to the git host before rerunning:"
  cat "${ssh_dir}/id_ed25519.pub"
  die "SSH key generated but not yet authorized on the git host."
}

prepare_logging() {
  mkdir -p "$LOG_DIR" || die "Cannot create log directory: ${LOG_DIR}"
  LOG_FILE="${LOG_DIR}/install_$(timestamp).log"
  exec > >(tee -a "$LOG_FILE") 2>&1
  log "Using configuration from ${CONFIG_SOURCE}"
}

build_preserve_paths() {
  PRESERVE_PATHS=()
  local item
  IFS=',' read -r -a raw_paths <<< "$PRESERVE_FILES"
  for item in "${raw_paths[@]}"; do
    item=$(printf '%s' "$item" | awk '{$1=$1; print}')
    [[ -n "$item" ]] && PRESERVE_PATHS+=("$item")
  done
  if [[ -n "$CONFIG_SOURCE" ]]; then
    local config_abs
    config_abs=$(cd "$(dirname "$CONFIG_SOURCE")" && pwd)/$(basename "$CONFIG_SOURCE")
    if [[ "$config_abs" == "$APPDIR"/* ]]; then
      PRESERVE_PATHS+=("${config_abs#${APPDIR}/}")
    fi
  fi
}

path_is_preserved() {
  local path=$1
  local item
  for item in "${PRESERVE_PATHS[@]}"; do
    [[ -z "$item" ]] && continue
    if [[ "$item" == */ ]]; then
      [[ "$path" == "$item"* ]] && return 0
    else
      [[ "$path" == "$item" ]] && return 0
    fi
  done
  return 1
}

path_is_managed_generated() {
  local path=$1
  local rel_static_dir=""

  if [[ "$STATIC_DIR" == "$APPDIR"/* ]]; then
    rel_static_dir="${STATIC_DIR#${APPDIR}/}"
  fi

  if [[ -n "$rel_static_dir" ]]; then
    case "$path" in
      "$rel_static_dir"|"$rel_static_dir"/*)
        return 0
        ;;
    esac
  fi

  case "$path" in
    staticfiles|staticfiles/*)
      return 0
      ;;
  esac

  return 1
}

backup_preserved_files() {
  TMP_PRESERVE=$(mktemp -d)
  local rel_path
  for rel_path in "${PRESERVE_PATHS[@]}"; do
    if [[ -e "${APPDIR}/${rel_path}" ]]; then
      mkdir -p "${TMP_PRESERVE}/$(dirname "$rel_path")"
      cp -a "${APPDIR}/${rel_path}" "${TMP_PRESERVE}/${rel_path}"
    fi
  done
}

restore_preserved_files() {
  if [[ -n "$TMP_PRESERVE" && -d "$TMP_PRESERVE" ]]; then
    if find "$TMP_PRESERVE" -mindepth 1 -print -quit | grep -q .; then
      cp -a "${TMP_PRESERVE}/." "$APPDIR/"
    fi
  fi
}

guard_unexpected_git_changes() {
  if [[ "$FORCE_RESET" -eq 1 ]]; then
    return 0
  fi

  local unexpected=()
  local line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    line=${line:3}
    if path_is_preserved "$line" || path_is_managed_generated "$line" || [[ "$line" == .env || "$line" == .env.* ]]; then
      continue
    fi
    unexpected+=("$line")
  done < <(git status --porcelain --untracked-files=all)
  if ((${#unexpected[@]})); then
    printf '%s\n' "${unexpected[@]}" | sed 's/^/ - /'
      # ensure terminal is sane before aborting so user can see the message
      restore_tty
    die "Repository has unexpected local changes. Commit them, remove them, add them to PRESERVE_FILES, or rerun with --force-reset to discard them."
  fi
}

clone_repository() {
  local repo=$1
  mkdir -p "$(dirname "$APPDIR")"
  if [[ "$repo" =~ ^git@([^:]+): ]]; then
    ensure_ssh_known_host "${BASH_REMATCH[1]}"
    ensure_ssh_key "$repo"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would clone ${repo} branch ${GIT_BRANCH} into ${APPDIR}"
    return 0
  fi
  git clone --branch "$GIT_BRANCH" --single-branch "$repo" "$APPDIR"
}

update_repository() {
  cd "$APPDIR"
  local origin_url
  origin_url=$(git remote get-url origin)
  if [[ "$(canonical_repo_url "$origin_url")" != "$(canonical_repo_url "$REPO_URL")" ]]; then
    die "Configured REPO_URL (${REPO_URL}) does not match origin remote (${origin_url}). Refusing to update the wrong repository."
  fi
  build_preserve_paths
  guard_unexpected_git_changes
  backup_preserved_files
  if [[ "$REPO_URL" =~ ^git@([^:]+): ]]; then
    ensure_ssh_known_host "${BASH_REMATCH[1]}"
    ensure_ssh_key "$REPO_URL"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would fetch origin ${GIT_BRANCH} and reset working tree"
    return 0
  fi

  if [[ "$FORCE_RESET" -eq 1 ]]; then
    warn "--force-reset enabled; discarding unpreserved local changes before updating from origin"
    # try a non-interactive hard reset and clean to discard local changes that would block checkout
    git fetch --prune origin "$GIT_BRANCH"
    git reset --hard "origin/${GIT_BRANCH}"
    git clean -fd
    restore_preserved_files
    return 0
  fi

  git fetch --prune origin "$GIT_BRANCH"
  git checkout -B "$GIT_BRANCH" "origin/${GIT_BRANCH}"
  git reset --hard "origin/${GIT_BRANCH}"
  restore_preserved_files
}

prepare_repository() {
  if [[ "$USE_TCP" -eq 1 ]] && ! is_port_free "$PORT"; then
    die "Port ${PORT} is already in use."
  fi
  if [[ ! -d "$APPDIR" ]]; then
    log "Application directory does not exist; cloning repository"
    clone_repository "$REPO_URL"
    return 0
  fi
  if [[ -z "$(ls -A "$APPDIR" 2>/dev/null)" ]]; then
    log "Application directory exists but is empty; cloning repository"
    clone_repository "$REPO_URL"
    return 0
  fi
  if [[ ! -d "$APPDIR/.git" ]]; then
    local backup_path="${APPDIR}.bak.$(timestamp)"
    confirm "${APPDIR} exists but is not a git repository. Move it to ${backup_path} and clone a fresh checkout?" || die "Refusing to overwrite a non-git application directory."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "DRY-RUN: would move ${APPDIR} to ${backup_path} and clone a fresh checkout"
      return 0
    fi
    mv "$APPDIR" "$backup_path"
    clone_repository "$REPO_URL"
    return 0
  fi
  log "Application directory already contains a git checkout; updating in place"
  update_repository
}

ensure_socket_directory() {
  if [[ "$USE_TCP" -eq 1 ]]; then
    return 0
  fi
  local socket_dir
  socket_dir=$(dirname "$SOCKET_PATH")
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would ensure socket directory ${socket_dir} exists and is owned by ${DEPLOY_USER}"
    return 0
  fi
  mkdir -p "$socket_dir"
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "$socket_dir" 2>/dev/null || true
  chmod 755 "$socket_dir" 2>/dev/null || true
}

ensure_virtualenv() {
  if [[ -x "${VENV_PATH}/bin/python" ]]; then
    return 0
  fi
  select_system_python
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would create virtualenv at ${VENV_PATH} with ${SYSTEM_PYTHON_BIN}"
    return 0
  fi
  mkdir -p "$(dirname "$VENV_PATH")"
  "$SYSTEM_PYTHON_BIN" -m venv "$VENV_PATH"
}

ensure_runtime_env() {
  ENV_FILE="${APPDIR}/.env"
  if [[ -f "$ENV_FILE" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "DRY-RUN: would ensure DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} in ${ENV_FILE}"
      return 0
    fi
    upsert_env_value "$ENV_FILE" "DJANGO_SETTINGS_MODULE" "${DJANGO_SETTINGS_MODULE}"
    chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
    chmod 600 "$ENV_FILE"
    return 0
  fi
  if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
    die "Runtime env file is missing: ${ENV_FILE}"
  fi
  confirm "Runtime env file ${ENV_FILE} does not exist. Create it now?" || die "Runtime env file is required."
  local secret_key allowed_hosts db_name db_user db_password db_host db_port
  secret_key=$(ask_secret "Django SECRET_KEY (leave empty to auto-generate)" "") || die "SECRET_KEY prompt cancelled"
  if [[ -z "$secret_key" ]]; then
    secret_key=$(
      python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(50))
PY
    )
  fi
  allowed_hosts=$(ask "ALLOWED_HOSTS (comma-separated)" "${DOMAIN},127.0.0.1,localhost") || die "ALLOWED_HOSTS prompt cancelled"
  db_name=$(ask "Database name (optional if settings module hardcodes it)" "") || die "Database name prompt cancelled"
  db_user=$(ask "Database user (optional)" "") || die "Database user prompt cancelled"
  db_password=$(ask_secret "Database password (optional)" "") || die "Database password prompt cancelled"
  db_host=$(ask "Database host" "127.0.0.1") || die "Database host prompt cancelled"
  db_port=$(ask "Database port" "3306") || die "Database port prompt cancelled"
  # sanitize inputs to remove accidental newlines from prompts
  secret_key=$(sanitize "$secret_key")
  allowed_hosts=$(sanitize "$allowed_hosts")
  db_name=$(sanitize "$db_name")
  db_user=$(sanitize "$db_user")
  db_password=$(sanitize "$db_password")
  db_host=$(sanitize "$db_host")
  db_port=$(sanitize "$db_port")
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would create ${ENV_FILE}"
    return 0
  fi
  mkdir -p "$APPDIR"
  cat > "$ENV_FILE" <<EOF
DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}
SECRET_KEY='${secret_key}'
ALLOWED_HOSTS='${allowed_hosts}'
DATABASE_NAME='${db_name}'
DATABASE_USER='${db_user}'
DATABASE_PASSWORD='${db_password}'
DATABASE_HOST='${db_host}'
DATABASE_PORT='${db_port}'
EOF
  # Ask for admin account to create (DJANGO_SUPERUSER_* env vars)
  if [[ "$NON_INTERACTIVE" -eq 0 ]]; then
    admin_user=$(ask "Django admin username (leave empty to skip creating admin)" "admin") || die "Admin username prompt cancelled"
    if [[ -n "$admin_user" ]]; then
      admin_email=$(ask "Django admin email (optional)" "") || die "Admin email prompt cancelled"
      admin_pass=$(ask_secret "Django admin password (leave empty to create interactively later)" "") || die "Admin password prompt cancelled"
    fi
  else
    admin_user=""
    admin_email=""
    admin_pass=""
  fi
  if [[ -n "$admin_user" ]]; then
    admin_user=$(sanitize "$admin_user")
    admin_email=$(sanitize "$admin_email")
    admin_pass=$(sanitize "$admin_pass")
    cat >> "$ENV_FILE" <<EOF
DJANGO_SUPERUSER_USERNAME='${admin_user}'
DJANGO_SUPERUSER_EMAIL='${admin_email}'
DJANGO_SUPERUSER_PASSWORD='${admin_pass}'
EOF
  fi
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
  chmod 600 "$ENV_FILE"
}

create_admin_user() {
  # Create Django superuser if DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD set in env
  local venv_python="${VENV_PATH}/bin/python"
  [[ -x "$venv_python" ]] || { warn "Virtualenv python not found; cannot create admin user"; return 0; }
  if [[ ! -f "${ENV_FILE}" ]]; then
    warn "Runtime env not found; skipping admin creation"
    return 0
  fi
  # Load env to pick up DJANGO_SUPERUSER_* values
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
  if [[ -z "${DJANGO_SUPERUSER_USERNAME:-}" || -z "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
    log "DJANGO_SUPERUSER_* not set or incomplete; skipping automatic superuser creation"
    return 0
  fi
  (
    cd "${APPDIR}"
    PYTHONPATH="${APPDIR}" "$venv_python" - <<PY
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE','${DJANGO_SETTINGS_MODULE}'))
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.getenv('DJANGO_SUPERUSER_USERNAME')
email = os.getenv('DJANGO_SUPERUSER_EMAIL','')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
if not username or not password:
    print('No superuser credentials provided; skipping')
else:
    if User.objects.filter(username=username).exists():
        print('Superuser exists; skipping')
    else:
        User.objects.create_superuser(username=username, email=email, password=password)
        print('Superuser created')
PY
  )
}

render_instance_settings_files() {
  local settings_dir="${APPDIR}/ecatalogus"
  local module_name="${DJANGO_SETTINGS_MODULE##*.}"
  local settings_file="${settings_dir}/${module_name}.py"
  local alias_file="${settings_dir}/settings.py"
  local instance_slug="${module_name#settings_}"
  local default_db_name="${SERVICE_SHORTNAME:-$instance_slug}"
  local default_allowed_hosts="${DOMAIN},127.0.0.1,localhost"
  local default_csrf_origins="https://${DOMAIN},http://${DOMAIN},https://127.0.0.1,http://127.0.0.1"
  local default_cors_origins="https://${DOMAIN},http://${DOMAIN},http://localhost:3000,http://localhost:8000"

  if [[ "$module_name" != settings_* ]]; then
    warn "No managed instance settings template for ${DJANGO_SETTINGS_MODULE}; skipping settings file rendering"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would render ${settings_file} and ${alias_file}"
    return 0
  fi

  mkdir -p "$settings_dir"
  cat > "$settings_file" <<EOF
"""Managed by scripts/install_instance.sh for ${DOMAIN}."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
  globals(),
  instance_slug='${instance_slug}',
  defaults={
    'domain': '${DOMAIN}',
    'overlay_dir': 'static_${instance_slug}',
    'database_name': '${default_db_name}',
    'database_user': 'ecatalogus_user',
    'public_url': 'https://${DOMAIN}',
    'allowed_hosts': ${default_allowed_hosts@Q}.split(','),
    'csrf_trusted_origins': ${default_csrf_origins@Q}.split(','),
    'cors_allowed_origins': ${default_cors_origins@Q}.split(','),
    'database_options': {
      'charset': '${DB_CHARSET}',
      'init_command': 'SET NAMES ${DB_CHARSET} COLLATE ${DB_COLLATION}',
    },
  },
)
EOF

  cat > "$alias_file" <<EOF
"""Managed default settings alias for ${DOMAIN}."""

from .${module_name} import *
EOF

  chown "${DEPLOY_USER}:${DEPLOY_USER}" "$settings_file" "$alias_file" 2>/dev/null || true
  chmod 640 "$settings_file" "$alias_file" 2>/dev/null || true
}

load_runtime_env() {
  ENV_FILE="${APPDIR}/.env"
  [[ -f "$ENV_FILE" ]] || die "Runtime env file is missing: ${ENV_FILE}"
  local configured_settings_module="$DJANGO_SETTINGS_MODULE"
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  if [[ "${DJANGO_SETTINGS_MODULE:-}" != "$configured_settings_module" ]]; then
    warn "Runtime env DJANGO_SETTINGS_MODULE (${DJANGO_SETTINGS_MODULE:-unset}) differs from installer config (${configured_settings_module}); using installer config."
    DJANGO_SETTINGS_MODULE="$configured_settings_module"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      upsert_env_value "$ENV_FILE" "DJANGO_SETTINGS_MODULE" "${DJANGO_SETTINGS_MODULE}"
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
      chmod 600 "$ENV_FILE"
    fi
  fi
  export DJANGO_SETTINGS_MODULE
}

validate_settings_module() {
  local venv_python="${VENV_PATH}/bin/python"
  [[ -x "$venv_python" ]] || die "Virtualenv Python not found: ${venv_python}"
  PYTHONPATH="$APPDIR" "$venv_python" - <<PY
import importlib
import sys

module_name = ${DJANGO_SETTINGS_MODULE@Q}
try:
    importlib.import_module(module_name)
except Exception as exc:
    print(f"Failed to import {module_name}: {exc}", file=sys.stderr)
    raise
PY
}

install_dependencies() {
  local venv_python="${VENV_PATH}/bin/python"
  local venv_pip="${VENV_PATH}/bin/pip"
  [[ -x "$venv_pip" ]] || die "Virtualenv pip not found: ${venv_pip}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would upgrade pip and install requirements.txt"
    return 0
  fi
  "$venv_python" -m pip install --upgrade pip
  if [[ -f "${APPDIR}/requirements.txt" ]]; then
    "$venv_pip" install -r "${APPDIR}/requirements.txt"
  else
    warn "requirements.txt not found in ${APPDIR}; skipping dependency installation"
  fi
  # ensure gunicorn is available inside the venv (prefer project-local runtime)
  if ! "$venv_python" -c 'import importlib,sys
import importlib.util
sys.exit(0 if importlib.util.find_spec("gunicorn") else 1)'; then
    log "gunicorn not found in venv; installing gunicorn into venv"
    "$venv_pip" install gunicorn
  fi
}

run_download_libs() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would run download_libs.sh in ${APPDIR}"
    return 0
  fi
  if [[ -f "${APPDIR}/download_libs.sh" ]]; then
    log "Running download_libs.sh in ${APPDIR}"
    (cd "${APPDIR}" && bash ./download_libs.sh)
  else
    warn "download_libs.sh not found in ${APPDIR}; skipping frontend asset download"
  fi
}

run_manage() {
  local venv_python="${VENV_PATH}/bin/python"
  [[ -x "$venv_python" ]] || die "Virtualenv Python not found: ${venv_python}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would run manage.py $*"
    return 0
  fi
  (
    cd "$APPDIR"
    "$venv_python" manage.py "$@"
  )
}

ensure_parent_traversal() {
  local target_path=$1
  local current_path

  current_path=$(dirname "$target_path")
  while [[ -n "$current_path" && "$current_path" != "/" ]]; do
    chmod o+x "$current_path" 2>/dev/null || true
    current_path=$(dirname "$current_path")
  done
}

get_django_database_config() {
  local venv_python="${VENV_PATH}/bin/python"
  [[ -x "$venv_python" ]] || die "Virtualenv Python not found: ${venv_python}"
  PYTHONPATH="$APPDIR" "$venv_python" - <<'PY'
import importlib
import os

module_name = os.environ['DJANGO_SETTINGS_MODULE']
settings = importlib.import_module(module_name)
database = settings.DATABASES['default']
print(database.get('NAME', ''))
print(database.get('USER', ''))
print(database.get('PASSWORD', ''))
print(database.get('HOST', ''))
print(database.get('PORT', ''))
PY
}

select_mysql_client() {
  if command -v mysql >/dev/null 2>&1; then
    printf '%s\n' "$(command -v mysql)"
    return 0
  fi
  if command -v mariadb >/dev/null 2>&1; then
    printf '%s\n' "$(command -v mariadb)"
    return 0
  fi
  return 1
}

ensure_database_charset() {
  local mysql_client
  mysql_client=$(select_mysql_client) || die "mysql/mariadb client not found; cannot enforce database charset"

  local db_name db_user db_password db_host db_port
  mapfile -t db_config < <(get_django_database_config)
  db_name=${db_config[0]:-}
  db_user=${db_config[1]:-}
  db_password=${db_config[2]:-}
  db_host=${db_config[3]:-127.0.0.1}
  db_port=${db_config[4]:-3306}

  [[ -n "$db_name" ]] || die "Database name is empty; cannot enforce database charset"
  [[ -n "$db_user" ]] || die "Database user is empty; cannot enforce database charset"

  local mysql_args=(--default-character-set="$DB_CHARSET" -h "$db_host" -P "$db_port" -u "$db_user")

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would create/alter database ${db_name} with ${DB_CHARSET}/${DB_COLLATION} and convert all existing tables"
    return 0
  fi

  MYSQL_PWD="$db_password" "$mysql_client" "${mysql_args[@]}" <<SQL
CREATE DATABASE IF NOT EXISTS \`$db_name\` CHARACTER SET ${DB_CHARSET} COLLATE ${DB_COLLATION};
ALTER DATABASE \`$db_name\` CHARACTER SET ${DB_CHARSET} COLLATE ${DB_COLLATION};
SQL

  local table_name
  while IFS= read -r table_name; do
    [[ -n "$table_name" ]] || continue
    MYSQL_PWD="$db_password" "$mysql_client" "${mysql_args[@]}" <<SQL
ALTER TABLE \`$db_name\`.\`$table_name\` CONVERT TO CHARACTER SET ${DB_CHARSET} COLLATE ${DB_COLLATION};
SQL
  done < <(
    MYSQL_PWD="$db_password" "$mysql_client" "${mysql_args[@]}" -N -s -e \
      "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='${db_name}' AND TABLE_TYPE='BASE TABLE'"
  )

  log "Ensured database ${db_name} and existing tables use ${DB_CHARSET}/${DB_COLLATION}"
}

link_public_assets() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would refresh media/static symlinks under ${PUBLIC_HTML}"
    return 0
  fi
  resolve_instance_runtime_paths

  local legacy_media_dir="${APPDIR}/media"
  local public_media_dir="${PUBLIC_HTML}/media"

  migrate_legacy_media_dir() {
    local source_dir="$1"
    if [[ ! -d "$source_dir" || "$MEDIA_DIR" == "$source_dir" ]]; then
      return 0
    fi

    mkdir -p "$MEDIA_DIR"
    if [[ -z "$(find "$MEDIA_DIR" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
      cp -a "${source_dir}/." "$MEDIA_DIR/"
      log "Migrated legacy media from ${source_dir} to ${MEDIA_DIR}"
    else
      log "Skipping legacy media migration from ${source_dir} because ${MEDIA_DIR} already contains files"
    fi
  }

  migrate_legacy_media_dir "$legacy_media_dir"

  if [[ -L "$public_media_dir" ]]; then
    local public_media_target=""
    public_media_target=$(readlink -f "$public_media_dir" 2>/dev/null || true)
    if [[ -n "$public_media_target" ]]; then
      migrate_legacy_media_dir "$public_media_target"
    fi
  elif [[ -d "$public_media_dir" ]]; then
    migrate_legacy_media_dir "$public_media_dir"
    rm -rf "$public_media_dir"
  fi

  # Ensure directories exist
  mkdir -p "$PUBLIC_HTML"
  mkdir -p "$MEDIA_DIR" "$STATIC_DIR"

  # Create/replace symlinks (use absolute paths to avoid confusion)
  if ln -sfn "$MEDIA_DIR" "$PUBLIC_HTML/media"; then
    log "Linked ${PUBLIC_HTML}/media -> ${MEDIA_DIR}"
  else
    warn "Failed to link ${PUBLIC_HTML}/media -> ${MEDIA_DIR}"
  fi

  if ln -sfn "$STATIC_DIR" "$PUBLIC_HTML/static"; then
    log "Linked ${PUBLIC_HTML}/static -> ${STATIC_DIR}"
  else
    warn "Failed to link ${PUBLIC_HTML}/static -> ${STATIC_DIR}"
  fi

  # Ensure ownership and reasonable permissions on targets
  if chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "$MEDIA_DIR" "$STATIC_DIR" 2>/dev/null; then
    log "Set owner ${DEPLOY_USER}:${DEPLOY_USER} on media and static directories"
  fi
  if chown -h "${DEPLOY_USER}:${DEPLOY_USER}" "$PUBLIC_HTML/media" "$PUBLIC_HTML/static" 2>/dev/null; then
    log "Set symlink owner for public_html entries"
  fi
  chmod -R u+rwX,g+rX,o+rX "$MEDIA_DIR" "$STATIC_DIR" 2>/dev/null || true
  ensure_parent_traversal "$STATIC_DIR"
  ensure_parent_traversal "$MEDIA_DIR"
  ensure_parent_traversal "$PUBLIC_HTML"
}

save_effective_config() {
  local out_conf="${SCRIPT_DIR}/config/${DOMAIN}.env"
  if [[ "$CONFIG_WAS_PROVIDED" -eq 1 && -n "$CONFIG_SOURCE" ]]; then
    out_conf="$CONFIG_SOURCE"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would save effective config to ${out_conf}"
    return 0
  fi
  mkdir -p "$(dirname "$out_conf")"
  cat > "$out_conf" <<EOF
DOMAIN=${DOMAIN}
DEPLOY_USER=${DEPLOY_USER}
REPO_URL=${REPO_URL}
GIT_BRANCH=${GIT_BRANCH}
APPDIR=${APPDIR}
VENV_PATH=${VENV_PATH}
SERVICE_SHORTNAME=${SERVICE_SHORTNAME}
USE_TCP=${USE_TCP}
PORT=${PORT}
SOCKET_PATH=${SOCKET_PATH}
STATIC_DIR=${STATIC_DIR}
MEDIA_DIR=${MEDIA_DIR}
PUBLIC_HTML=${PUBLIC_HTML}
LOG_DIR=${LOG_DIR}
DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}
PRESERVE_FILES=${PRESERVE_FILES}
PYTHON_BIN=${PYTHON_BIN}
TCP_BIND_HOST=${TCP_BIND_HOST}
EOF
  log "Saved effective config to ${out_conf}"
}

render_service() {
  local service_out="${SCRIPT_DIR}/../deploy/gunicorn_${SERVICE_SHORTNAME}.service"
  local template="${SCRIPT_DIR}/../deploy/gunicorn.service.template"
  local bind_arg=""
  [[ -f "$template" ]] || die "Service template not found: ${template}"
  if [[ "$USE_TCP" -eq 1 ]]; then
    bind_arg="--bind ${TCP_BIND_HOST}:${PORT}"
  else
    bind_arg="--bind unix:${SOCKET_PATH}"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would render systemd unit to ${service_out}"
    return 0
  fi
  mkdir -p "${SCRIPT_DIR}/../deploy"
  # choose gunicorn binary: prefer venv, fall back to system gunicorn
  local chosen_gunicorn path_val
  if [[ -x "${VENV_PATH}/bin/gunicorn" ]]; then
    chosen_gunicorn="${VENV_PATH}/bin/gunicorn"
    path_val="${VENV_PATH}/bin"
  else
    if command -v gunicorn >/dev/null 2>&1; then
      chosen_gunicorn=$(command -v gunicorn)
      path_val=$(dirname "$chosen_gunicorn")
    else
      die "No gunicorn binary found in ${VENV_PATH}/bin and no system gunicorn available. Install gunicorn or create virtualenv."
    fi
  fi
  # compute PYTHONPATH: always include APPDIR; if venv exists, add its site-packages
  local py_path
  py_path="${APPDIR}"
  if [[ -x "${VENV_PATH}/bin/python" ]]; then
    # attempt to discover site-packages path from venv python
    local venv_site
    venv_site=$("${VENV_PATH}/bin/python" -c 'import site, sys; s=site.getsitepackages(); print(s[0] if s else "")' 2>/dev/null || true)
    if [[ -n "$venv_site" ]]; then
      py_path="${APPDIR}:$venv_site"
    fi
  fi
  sed -e "s|{SERVICE_SHORTNAME}|${SERVICE_SHORTNAME}|g" \
      -e "s|{APPDIR}|${APPDIR}|g" \
      -e "s|{VENV_PATH}|${VENV_PATH}|g" \
      -e "s|{SOCKET_PATH}|${SOCKET_PATH}|g" \
      -e "s|{PORT}|${PORT}|g" \
      -e "s|{DJANGO_SETTINGS_MODULE}|${DJANGO_SETTINGS_MODULE}|g" \
      -e "s|{BIND}|${bind_arg}|g" \
      -e "s|{ENV_FILE}|${ENV_FILE}|g" \
      -e "s|{DEPLOY_USER}|${DEPLOY_USER}|g" \
      -e "s|{WORKERS}|3|g" \
      -e "s|{WSGI_MODULE}|ecatalogus.wsgi|g" \
      -e "s|{GUNICORN_BIN}|${chosen_gunicorn}|g" \
      -e "s|{PATH}|${path_val}|g" \
      -e "s|{PYTHONPATH}|${py_path}|g" \
      "$template" > "$service_out"
  log "Rendered systemd unit to ${service_out}"
}

render_nginx_snippet() {
  local out_snippet="${SCRIPT_DIR}/../deploy/nginx_${SERVICE_SHORTNAME}_custom3.conf"
  resolve_instance_runtime_paths
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would render DirectAdmin nginx CUSTOM3 snippet to ${out_snippet}"
    return 0
  fi
  mkdir -p "${SCRIPT_DIR}/../deploy"
  cat > "$out_snippet" <<EOF
location = /favicon.ico {
    access_log off;
    log_not_found off;
}

location /static/ {
  alias ${STATIC_DIR}/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}

location /media/ {
  alias ${MEDIA_DIR}/;
    expires 30d;
    add_header Cache-Control "public, immutable";

    # Optional: large file handling and range requests
    sendfile on;
    tcp_nopush on;
}

location / {
    proxy_pass http://unix:${PUBLIC_HTML}/gunicorn.sock;
  proxy_set_header Host \$host;
  proxy_set_header X-Real-IP \$remote_addr;
  proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto \$scheme;

    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;
}
EOF
  log "Rendered DirectAdmin nginx CUSTOM3 snippet to ${out_snippet}"
}

install_directadmin_snippet() {
  local snippet_src="${SCRIPT_DIR}/../deploy/nginx_${SERVICE_SHORTNAME}_custom3.conf"
  [[ -f "$snippet_src" ]] || die "Nginx snippet not found: ${snippet_src}"

  # If running as root, try to copy into DirectAdmin user domain folder
  if [[ $EUID -eq 0 ]]; then
    local da_user_dir="/usr/local/directadmin/data/users/${DEPLOY_USER}/domains"
    local target_file="${da_user_dir}/${DOMAIN}.conf"
    if [[ -d "${da_user_dir}" ]]; then
      mkdir -p "${da_user_dir}"
      if [[ -f "${target_file}" ]]; then
        cp -a "${target_file}" "${target_file}.bak_$(timestamp)" || true
      fi
      # Append CUSTOM3 marker and snippet (DirectAdmin UI uses specific format; we append as CUSTOM3)
      printf "\n# CUSTOM3 (added by installer)\n" >> "${target_file}"
      cat "$snippet_src" >> "${target_file}"
      log "Appended CUSTOM3 snippet into ${target_file}"

      # Try to run DirectAdmin custombuild rewrite_confs if available
      if [[ -x "/usr/local/directadmin/custombuild/build" ]]; then
        /usr/local/directadmin/custombuild/build rewrite_confs || warn "custombuild rewrite_confs failed"
      elif [[ -x "/usr/local/directadmin/scripts/rewrite_confs.sh" ]]; then
        /usr/local/directadmin/scripts/rewrite_confs.sh || warn "rewrite_confs.sh failed"
      else
        warn "Could not find DirectAdmin build script; you may need to run 'build rewrite_confs' manually"
      fi
      return 0
    else
      warn "DirectAdmin user domains directory not found: ${da_user_dir}; not installing snippet automatically"
    fi
  else
    log "Not running as root — saved DirectAdmin nginx snippet to ${snippet_src}. To install it manually, copy its contents into the DirectAdmin Custom HTTPD Configurations (CUSTOM3) for domain ${DOMAIN} and run the DirectAdmin build rewrite_confs command as root."
  fi
}

install_unit_file() {
  [[ "$INSTALL_UNIT" -eq 1 ]] || return 0
  local service_out="${SCRIPT_DIR}/../deploy/gunicorn_${SERVICE_SHORTNAME}.service"
  local target_unit="/etc/systemd/system/gunicorn_${SERVICE_SHORTNAME}.service"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would install ${service_out} to ${target_unit} and enable the service"
    return 0
  fi
  [[ -f "$service_out" ]] || die "Rendered service file not found: ${service_out}"
  if [[ $EUID -eq 0 ]]; then
    cp -f "$service_out" "$target_unit"
    systemctl daemon-reload
    systemctl enable --now "gunicorn_${SERVICE_SHORTNAME}.service"
    return 0
  fi
  if sudo -n true 2>/dev/null; then
    sudo cp -f "$service_out" "$target_unit"
    sudo systemctl daemon-reload
    sudo systemctl enable --now "gunicorn_${SERVICE_SHORTNAME}.service"
    return 0
  fi
  # Not running as root and no passwordless sudo: do not fail, print manual instructions instead
  warn "--install-unit was requested but root or passwordless sudo is not available. The service file was rendered but not installed."
  log "To install the service as root, run the following commands on the server as root or via sudo:"
  cat <<CMDS
cp "${service_out}" "${target_unit}"
systemctl daemon-reload
systemctl enable --now "gunicorn_${SERVICE_SHORTNAME}.service"
journalctl -u "gunicorn_${SERVICE_SHORTNAME}" -f
CMDS
  return 0
}

prompt_for_missing_config_if_needed() {
  if [[ "$CONFIG_WAS_PROVIDED" -eq 1 && "$EDIT_CONFIG" -eq 0 ]]; then
    return 0
  fi
  if show_config_form; then
    return 0
  fi
  if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
    return 0
  fi
  DOMAIN=$(ask "Domain" "$DOMAIN") || die "Domain prompt cancelled"
  DEPLOY_USER=$(ask "Deploy user" "$DEPLOY_USER") || die "Deploy user prompt cancelled"
  REPO_URL=$(ask "Repository URL" "$REPO_URL") || die "Repository URL prompt cancelled"
  GIT_BRANCH=$(ask "Git branch" "$GIT_BRANCH") || die "Git branch prompt cancelled"
  APPDIR=$(ask "Application directory" "$APPDIR") || die "Application directory prompt cancelled"
  VENV_PATH=$(ask "Virtualenv path" "$VENV_PATH") || die "Virtualenv prompt cancelled"
  SERVICE_SHORTNAME=$(ask "Service shortname" "$SERVICE_SHORTNAME") || die "Service shortname prompt cancelled"
  USE_TCP=$(ask "Use TCP (1) or Unix socket (0)" "$USE_TCP") || die "Use TCP prompt cancelled"
  if [[ "$USE_TCP" == "1" ]]; then
    PORT=$(ask "Port" "$PORT") || die "Port prompt cancelled"
  else
    SOCKET_PATH=$(ask "Socket path" "$SOCKET_PATH") || die "Socket path prompt cancelled"
  fi
  PRESERVE_FILES=$(ask "Preserve files (comma-separated)" "$PRESERVE_FILES") || die "Preserve files prompt cancelled"
}

run_action_env() {
  ensure_runtime_env
  render_instance_settings_files
  if [[ "$DRY_RUN" -eq 0 ]]; then
    log "Runtime env is ready at ${APPDIR}/.env"
  fi
}

run_action_venv() {
  ensure_virtualenv
  log "Virtualenv is ready at ${VENV_PATH}"
}

run_action_full() {
  ensure_socket_directory
  update_gauge 5 "Preparing repository"
  prepare_repository
  update_gauge 25 "Preparing virtualenv"
  ensure_virtualenv
  update_gauge 40 "Ensuring runtime env"
  ensure_runtime_env
  update_gauge 45 "Rendering instance settings"
  render_instance_settings_files
  load_runtime_env
  update_gauge 48 "Rendering deploy files"
  save_effective_config
  render_service
  render_nginx_snippet
  update_gauge 50 "Installing dependencies"
  install_dependencies
  update_gauge 55 "Fetching frontend libraries"
  run_download_libs
  update_gauge 60 "Enforcing database charset"
  ensure_database_charset
  update_gauge 65 "Validating settings"
  validate_settings_module
  update_gauge 75 "Running Django checks"
  run_manage check
  update_gauge 85 "Applying migrations"
  run_manage migrate --noinput
  # Attempt to create admin user if credentials were provided in .env
  create_admin_user
  update_gauge 92 "Collecting static files"
  run_manage collectstatic --noinput
  update_gauge 96 "Refreshing symlinks"
  link_public_assets
  update_gauge 98 "Installing generated configs"
  install_unit_file
  install_directadmin_snippet
  # If the systemd unit was not installed automatically, print manual instructions
  if [[ "$INSTALL_UNIT" -ne 1 ]]; then
    local service_out="${SCRIPT_DIR}/../deploy/gunicorn_${SERVICE_SHORTNAME}.service"
    local snippet_out="${SCRIPT_DIR}/../deploy/nginx_${SERVICE_SHORTNAME}_custom3.conf"
    local target_unit="/etc/systemd/system/gunicorn_${SERVICE_SHORTNAME}.service"
    log "Systemd unit was rendered to: ${service_out}"
    log "DirectAdmin CUSTOM3 snippet was rendered to: ${snippet_out}"
    log "To install and start the unit as root, run the following commands:"
    cat <<CMDS
cp "${service_out}" "${target_unit}"
systemctl daemon-reload
systemctl enable --now "gunicorn_${SERVICE_SHORTNAME}.service"
journalctl -u "gunicorn_${SERVICE_SHORTNAME}" -f
CMDS
  fi
  update_gauge 100 "Completed"
}

main() {
  parse_args "$@"
  ensure_required_commands
  load_config
  # resolve template values so APPDIR/VENV_PATH/etc are available for prompts and logging
  resolve_config
  prompt_for_missing_config_if_needed
  # re-resolve in case the interactive prompts changed template values
  resolve_config
  validate_required
  prepare_logging
  log "Using configuration from ${CONFIG_SOURCE}"
  if ! show_main_menu; then
    log "Aborted by user"
    exit 0
  fi
  ACTION="$ACTION_SELECTED"
  log "Selected action: ${ACTION}"
  case "$ACTION" in
    full|"")
      start_gauge
      run_action_full
      ;;
    env)
      run_action_env
      ;;
    venv)
      run_action_venv
      ;;
    quit)
      log "Aborted by user"
      exit 0
      ;;
    *)
      die "Unsupported action: ${ACTION}"
      ;;
  esac
  log "Install finished successfully"
  [[ -n "$LOG_FILE" ]] && log "Install log: ${LOG_FILE}"
}

main "$@"
