#!/usr/bin/env bash
set -euo pipefail

# install_instance.sh
# Consolidated interactive installer for a Django instance using git, virtualenv and Gunicorn.
# Uses whiptail when available; falls back to stdin prompts. Renders deploy/gunicorn_${SERVICE_SHORTNAME}.service

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_ENV=${SCRIPT_DIR}/config/example.env

# CLI flags
INSTALL_UNIT=0
DRY_RUN=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [config.env] [--install-unit] [--dry-run]
  --install-unit   Install and enable generated systemd unit (requires root or sudo)
  --dry-run        Show actions without making changes
  -h|--help        Show this help
Examples:
  # Interactive install using repo config example
  $(basename "$0") scripts/config/example.env

  # Non-interactive using an existing per-domain config and install unit as root
  sudo $(basename "$0") scripts/config/ecatalogus.ispan.pl.env --install-unit

  # Dry-run for testing
  $(basename "$0") scripts/config/ecatalogus.ispan.pl.env --dry-run
EOF
}

while (( "$#" )); do
  case "$1" in
    --install-unit)
      INSTALL_UNIT=1; shift ;;
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *) break ;;
  esac
done

timestamp() { date +%Y%m%d-%H%M%S; }

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

ask() {
  local prompt=$1; local default=${2-}
  if command -v whiptail >/dev/null 2>&1; then
    local out
    out=$(whiptail --title "Installer" --inputbox "$prompt" 10 60 "$default" 3>&1 1>&2 2>&3)
    restore_tty
    echo "$out"
  else
    read -rp "$prompt [$default]: " ans </dev/tty
    echo "${ans:-$default}"
  fi
}

ask_secret() {
  local prompt=$1; local default=${2-}
  if command -v whiptail >/dev/null 2>&1; then
    local out
    out=$(whiptail --title "Installer" --passwordbox "$prompt" 10 60 3>&1 1>&2 2>&3)
    restore_tty
    echo "$out"
  else
    read -rsp "$prompt: " ans </dev/tty
    echo
    echo "${ans:-$default}"
  fi
}

is_port_free() {
  local port=$1
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$port" | grep -q LISTEN && return 1 || return 0
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 1 || return 0
  else
    return 1
  fi
}

# whiptail/gauge helpers
whiptail_ok() { command -v whiptail >/dev/null 2>&1; }
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
  local pct=$1; local msg=${2-}
  if [[ -n "${GAUGE_PID-}" ]]; then
    echo "$pct" >&3
    echo "$msg" >&3
  else
    log "PROGRESS: $pct% - $msg"
  fi
}
stop_gauge() {
  if [[ -n "${GAUGE_PID-}" ]]; then
    exec 3>&-
    wait "$GAUGE_PID" 2>/dev/null || true
    rm -f "$GAUGE_PIPE" 2>/dev/null || true
    unset GAUGE_PID
  fi
}

restore_tty() {
  # Restore terminal state after whiptail
  stty sane 2>/dev/null || true
  tput reset 2>/dev/null || true
  sleep 0.02
}

try_git_clone() {
  local repo=$1; local branch=$2; local dest=$3
  # Prefer non-interactive SSH (fail fast if no key)
  if GIT_SSH_COMMAND='ssh -o BatchMode=yes' git clone --branch "$branch" "$repo" "$dest"; then
    return 0
  fi
  # If repo is an SSH github URL and clone failed due to publickey, try HTTPS fallback
  if [[ "$repo" =~ ^git@github.com:(.+) ]]; then
    local path=${BASH_REMATCH[1]}
    local https_repo="https://github.com/${path}"
    log "SSH clone failed; retrying with HTTPS: $https_repo"
    if git clone --branch "$branch" "$https_repo" "$dest"; then
      return 0
    fi
  fi
  return 1
}

# whiptail menu (multi-screen) wrapper
show_main_menu() {
  if whiptail_ok; then
    CHOICE=$(whiptail --title "Installer Menu" --menu "Choose action" 15 60 4 \
      "1" "Full install (clone, venv, migrate, collectstatic)" \
      "2" "Create/Update .env (secrets)" \
      "3" "Create virtualenv only" \
      "4" "Quit" 3>&1 1>&2 2>&3)
    restore_tty
    echo "$CHOICE"
  else
    echo "1"
  fi
}

# multi-field config form using whiptail --form
show_config_form() {
  if ! whiptail_ok; then
    return 1
  fi
  local form_output
  form_output=$(whiptail --title "Instance configuration" --form "Edit fields (TAB to move)" 20 80 12 \
    "Domain" 1 1 "${DOMAIN}" 1 30 50 0 \
    "Deploy user" 2 1 "${DEPLOY_USER}" 2 30 50 0 \
    "Repository URL" 3 1 "${REPO_URL}" 3 30 50 0 \
    "Git branch" 4 1 "${GIT_BRANCH}" 4 30 50 0 \
    "App dir" 5 1 "${APPDIR}" 5 30 50 0 \
    "Venv path" 6 1 "${VENV_PATH}" 6 30 50 0 \
    "Service shortname" 7 1 "${SERVICE_SHORTNAME}" 7 30 50 0 \
    "Use TCP (0/1)" 8 1 "${USE_TCP}" 8 30 50 0 \
    "Port" 9 1 "${PORT}" 9 30 50 0 \
    "Socket path" 10 1 "${SOCKET_PATH}" 10 30 50 0 \
    "Preserve files (comma)" 11 1 "${PRESERVE_FILES}" 11 30 50 0 3>&1 1>&2 2>&3)
  # whiptail --form returns newline separated fields; read into variables
  if [[ -n "$form_output" ]]; then
    # read into array to avoid losing values if some fields are empty
    IFS=$'\n' read -r -a FORM_ARR <<<"$form_output"
    # assign back only when a field is non-empty, otherwise keep existing value
    DOMAIN=${FORM_ARR[0]:-$DOMAIN}
    DEPLOY_USER=${FORM_ARR[1]:-$DEPLOY_USER}
    REPO_URL=${FORM_ARR[2]:-$REPO_URL}
    GIT_BRANCH=${FORM_ARR[3]:-$GIT_BRANCH}
    APPDIR=${FORM_ARR[4]:-$APPDIR}
    VENV_PATH=${FORM_ARR[5]:-$VENV_PATH}
    SERVICE_SHORTNAME=${FORM_ARR[6]:-$SERVICE_SHORTNAME}
    USE_TCP=${FORM_ARR[7]:-$USE_TCP}
    PORT=${FORM_ARR[8]:-$PORT}
    SOCKET_PATH=${FORM_ARR[9]:-$SOCKET_PATH}
    PRESERVE_FILES=${FORM_ARR[10]:-$PRESERVE_FILES}
    restore_tty
    return 0
  fi
  return 1
}

# SELinux helper: warn if enforcing and provide suggested commands
check_selinux() {
  if command -v getenforce >/dev/null 2>&1; then
    local se
    se=$(getenforce 2>/dev/null || true)
    if [[ "$se" == "Enforcing" ]]; then
      log "SELinux appears to be enforcing on this host. You may need to set proper file contexts for socket and media/static dirs."
      log "Suggested commands (run as root):"
      log "  semanage fcontext -a -t httpd_var_run_t '${SOCKET_PATH}' || true"
      log "  restorecon -v '${SOCKET_PATH}' || true"
      log "  semanage fcontext -a -t httpd_sys_content_t '${APPDIR}/media(/.*)?' || true"
      log "  restorecon -R -v '${APPDIR}/media' || true"
    fi
  fi
}

# Validate socket ownership and permissions, attempt to fix when possible
validate_socket() {
  if [[ "${USE_TCP:-0}" == "1" ]]; then
    return 0
  fi
  local sock=$SOCKET_PATH
  local sdir
  sdir=$(dirname "$sock")
  # ensure socket dir exists
  if [[ ! -d "$sdir" ]]; then
    log "Creating socket directory $sdir"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      mkdir -p "$sdir"
    fi
  fi
  # ensure ownership
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if chown "${DEPLOY_USER}:${DEPLOY_USER}" "$sdir" 2>/dev/null; then
      log "Set owner of $sdir to ${DEPLOY_USER}:${DEPLOY_USER}"
    fi
    chmod 755 "$sdir" 2>/dev/null || true
  else
    log "DRY-RUN: would chown $sdir to ${DEPLOY_USER} and chmod 755"
  fi

  # If socket exists, check owner/perm and remove stale socket if not used
  if [[ -e "$sock" ]]; then
    if [[ -S "$sock" ]]; then
      # check ownership
      owner=$(stat -c '%U' "$sock" 2>/dev/null || stat -f '%Su' "$sock" 2>/dev/null || true)
      if [[ "$owner" != "${DEPLOY_USER}" ]]; then
        log "Socket $sock owner is $owner, expected ${DEPLOY_USER}. Attempting fix."
        if [[ "$DRY_RUN" -eq 0 ]]; then
          chown ${DEPLOY_USER}:${DEPLOY_USER} "$sock" 2>/dev/null || true
          chmod 660 "$sock" 2>/dev/null || true
        fi
      fi
    else
      # file exists but not a socket - warn and optionally remove
      log "Warning: $sock exists but is not a socket. Backing up and removing."
      if [[ "$DRY_RUN" -eq 0 ]]; then
        mv "$sock" "${sock}.bak.$(timestamp)" 2>/dev/null || true
      fi
    fi
  fi
}

write_settings_module() {
  local mod_name="ecatalogus.settings_${SERVICE_SHORTNAME}"
  local target_dir="$APPDIR/ecatalogus"
  local target_file="$target_dir/settings_${SERVICE_SHORTNAME}.py"

  mkdir -p "$target_dir"

  cat > "$target_file" <<'PY'
from .settings_base import *
import os

# Read runtime secrets from environment (APPDIR/.env should be sourced by systemd and scripts)
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')
DEBUG = os.environ.get('DEBUG', 'False') in ('True', 'true', '1')
ALLOWED_HOSTS = [h for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h]

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': os.environ.get('DATABASE_NAME', ''),
        'USER': os.environ.get('DATABASE_USER', ''),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', ''),
        'HOST': os.environ.get('DATABASE_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DATABASE_PORT', ''),
    }
}

PY

  log "Wrote per-instance settings module: $target_file"

  # ensure DJANGO_SETTINGS_MODULE is set in APPDIR/.env
  if [[ -f "$APPDIR/.env" ]]; then
    if ! grep -q '^DJANGO_SETTINGS_MODULE=' "$APPDIR/.env"; then
      echo "DJANGO_SETTINGS_MODULE=${mod_name}" >> "$APPDIR/.env"
      chmod 600 "$APPDIR/.env" || true
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$APPDIR/.env" 2>/dev/null || true
      log "Appended DJANGO_SETTINGS_MODULE=${mod_name} to $APPDIR/.env"
    else
      sed -i.bak -E "s|^DJANGO_SETTINGS_MODULE=.*|DJANGO_SETTINGS_MODULE=${mod_name}|" "$APPDIR/.env" || true
      log "Updated DJANGO_SETTINGS_MODULE in $APPDIR/.env"
    fi
  else
    # create minimal .env with DJANGO_SETTINGS_MODULE if missing
    cat > "$APPDIR/.env" <<EOF
DJANGO_SETTINGS_MODULE=${mod_name}
EOF
    chown "${DEPLOY_USER}:${DEPLOY_USER}" "$APPDIR/.env" 2>/dev/null || true
    chmod 600 "$APPDIR/.env" || true
    log "Created $APPDIR/.env with DJANGO_SETTINGS_MODULE=${mod_name}"
  fi
}

ensure_ssh_known_host() {
  # add common git host to known_hosts to avoid interactive prompt
  local host=${1:-github.com}
  local ssh_dir
  ssh_dir="${HOME}/.ssh"
  mkdir -p "$ssh_dir"
  chmod 700 "$ssh_dir" || true
  local kh="$ssh_dir/known_hosts"
  if command -v ssh-keyscan >/dev/null 2>&1; then
    # Only add if not already present
    if ! grep -q "^$host[ ,]" "$kh" 2>/dev/null; then
      log "Adding SSH host key for $host to $kh"
      if [[ "$DRY_RUN" -eq 0 ]]; then
        ssh-keyscan -t rsa,ecdsa,ed25519 "$host" >> "$kh" 2>/dev/null || true
        chmod 644 "$kh" || true
      else
        log "DRY-RUN: would ssh-keyscan $host >> $kh"
      fi
    fi
  else
    log "ssh-keyscan not available; if this is the first time connecting to $host you may be prompted to accept its host key."
  fi
}

ensure_ssh_key() {
  # If repo uses SSH and no key exists, offer to generate one
  local repo=$1
  if [[ "$repo" =~ ^git@ ]]; then
    local ssh_dir="$HOME/.ssh"
    if [[ ! -f "$ssh_dir/id_ed25519" && ! -f "$ssh_dir/id_rsa" ]]; then
      if whiptail_ok; then
        if whiptail --title "SSH key" --yesno "No SSH key found in $ssh_dir. Generate a new ed25519 key now? You will need to add its public key to GitHub." 10 70; then
          restore_tty
          DO_GEN=1
        else
          restore_tty
          DO_GEN=0
        fi
      else
        read -rp "No SSH key found. Generate now? [y/N]: " yn </dev/tty
        case "$yn" in [Yy]*) DO_GEN=1 ;; *) DO_GEN=0 ;; esac
      fi

      if [[ "$DO_GEN" -eq 1 ]]; then
        mkdir -p "$ssh_dir"; chmod 700 "$ssh_dir"
        ssh-keygen -t ed25519 -f "$ssh_dir/id_ed25519" -N "" -C "deploy@$(hostname)" || true
        chmod 600 "$ssh_dir/id_ed25519" || true
        log "Generated SSH key at $ssh_dir/id_ed25519. Public key:" 
        cat "$ssh_dir/id_ed25519.pub" || true
        if whiptail_ok; then
          whiptail --title "SSH key generated" --msgbox "Public key was printed to stdout. Add it to GitHub (repo deploy key or account SSH key), then continue." 10 70
          restore_tty
        else
          echo "Public key above. Add it to GitHub, then press Enter to continue." </dev/tty
          read -r _ </dev/tty
        fi
      fi
    fi
  fi
}

print_git_ssh_help() {
  cat >&2 <<'HELP'
Git clone failed due to SSH/publickey issues.
Possible remedies:
  1) Ensure the deploy user has an SSH key and added its public key to GitHub:
       ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "deploy@host"
       cat ~/.ssh/id_ed25519.pub
     Then add the printed key as a Deploy Key (repo) or SSH key (account) on GitHub.

  2) If you prefer HTTPS cloning temporarily, change REPO_URL in your config to:
       https://github.com/yourorg/ecatalogus.git
     Note: HTTPS may require a personal access token for private repos.

  3) To avoid host key prompts, run as the deploy user:
       mkdir -p ~/.ssh && chmod 700 ~/.ssh
       ssh-keyscan github.com >> ~/.ssh/known_hosts

After adding the key to GitHub, test with:
       ssh -T git@github.com
HELP
}

load_env() {
  if [[ -n "${1-}" && -f "$1" ]]; then
    # shellcheck source=/dev/null
    source "$1"
  elif [[ -f "$DEFAULT_ENV" ]]; then
    # shellcheck source=/dev/null
    source "$DEFAULT_ENV"
  else
    echo "No config file found and no defaults available." >&2
    exit 1
  fi
}

ensure_app_env() {
  # If APPDIR/.env exists, source it. Otherwise offer to create it interactively (secrets only).
  ENV_FILE="$APPDIR/.env"
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    log "Sourced secrets from $ENV_FILE"
    return 0
  fi

  if command -v whiptail >/dev/null 2>&1; then
    if whiptail --title "Create .env" --yesno "No ${ENV_FILE} found. Create one now (contains DB credentials and SECRET_KEY)?" 10 60; then
      restore_tty
      CREATE_ENV=1
    else
      restore_tty
      CREATE_ENV=0
    fi
  else
    read -rp "No ${ENV_FILE} found. Create now? [y/N]: " yn </dev/tty
    case "$yn" in
      [Yy]*) CREATE_ENV=1 ;;
      *) CREATE_ENV=0 ;;
    esac
  fi

  if [[ "$CREATE_ENV" -eq 1 ]]; then
    DB_NAME=$(ask "Database name" "${DATABASE_NAME-}")
    DB_USER=$(ask "Database user" "${DATABASE_USER-}")
    DB_PASSWORD=$(ask_secret "Database password")
    DB_HOST=$(ask "Database host" "${DATABASE_HOST:-127.0.0.1}")
    DB_PORT=$(ask "Database port" "${DATABASE_PORT:-5432}")
    SECRET_KEY_INPUT=$(ask_secret "Django SECRET_KEY (leave empty to generate)")
    if [[ -z "$SECRET_KEY_INPUT" ]]; then
      SECRET_KEY_INPUT=$(python3 - <<PY
import secrets
print(secrets.token_urlsafe(50))
PY
)
    fi
    ALLOWED_HOSTS_INPUT=$(ask "ALLOWED_HOSTS (comma-separated)" "${ALLOWED_HOSTS-}")

    cat > "$ENV_FILE" <<EOF
# secrets for instance (do not commit)
DATABASE_NAME=${DB_NAME}
DATABASE_USER=${DB_USER}
DATABASE_PASSWORD='${DB_PASSWORD}'
DATABASE_HOST=${DB_HOST}
DATABASE_PORT=${DB_PORT}
SECRET_KEY='${SECRET_KEY_INPUT}'
ALLOWED_HOSTS='${ALLOWED_HOSTS_INPUT}'
EOF
    chown ${DEPLOY_USER}:${DEPLOY_USER} "$ENV_FILE" 2>/dev/null || true
    chmod 600 "$ENV_FILE"
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    log "Created and sourced $ENV_FILE"
  else
    log "Skipping creation of $ENV_FILE; remember to create it before running manage commands."
  fi
}

render_service() {
  local out="$1"
  local tmpl="$SCRIPT_DIR/../deploy/gunicorn.service.template"
  if [[ ! -f "$tmpl" ]]; then
    echo "Service template $tmpl not found; skipping rendering." >&2
    return 0
  fi
  sed -e "s|{SERVICE_SHORTNAME}|${SERVICE_SHORTNAME}|g" \
      -e "s|{APPDIR}|${APPDIR}|g" \
      -e "s|{VENV_PATH}|${VENV_PATH}|g" \
      -e "s|{SOCKET_PATH}|${SOCKET_PATH-}|g" \
      -e "s|{PORT}|${PORT-}|g" \
      -e "s|{DJANGO_SETTINGS_MODULE}|${DJANGO_SETTINGS_MODULE}|g" \
      -e "s|{BIND}|${BIND-}|g" \
      -e "s|{ENV_FILE}|${ENV_FILE_PATH-}|g" \
      -e "s|{DEPLOY_USER}|${DEPLOY_USER}|g" \
      -e "s|{WORKERS}|3|g" \
      -e "s|{WSGI_MODULE}|ecatalogus.wsgi|g" \
      "$tmpl" > "$out"
}

main() {
  local cfg_arg=${1-}
  load_env "$cfg_arg"

  log "Using configuration from ${cfg_arg:-$DEFAULT_ENV}"
  # Interactive menu and overrides (whiptail or stdin)
  MENU_CHOICE=$(show_main_menu)
  if [[ "$MENU_CHOICE" == "2" ]]; then
    ensure_app_env
    echo "Created/updated .env (if requested). Exiting."; exit 0
  elif [[ "$MENU_CHOICE" == "3" ]]; then
    # create virtualenv only
    APPDIR=$(ask "Application directory" "$APPDIR")
    VENV_PATH=$(ask "Virtualenv path" "${VENV_PATH:-$APPDIR/.venv}")
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "DRY-RUN: would create venv at $VENV_PATH"
      exit 0
    else
      mkdir -p "$APPDIR"
      python3.11 -m venv "$VENV_PATH"
      echo "Virtualenv created at $VENV_PATH"; exit 0
    fi
  elif [[ "$MENU_CHOICE" == "4" ]]; then
    echo "Aborted by user."; exit 0
  fi

  # Prefer multi-field form when whiptail is available
  if whiptail_ok && show_config_form; then
    log "Configuration updated via form"
  else
    DOMAIN=$(ask "Domain" "$DOMAIN")
    DEPLOY_USER=$(ask "Deploy user" "$DEPLOY_USER")
    REPO_URL=$(ask "Repository URL (git)" "$REPO_URL")
    GIT_BRANCH=$(ask "Git branch" "$GIT_BRANCH")
    APPDIR=$(ask "Application directory" "$APPDIR")
    VENV_PATH=$(ask "Virtualenv path" "${VENV_PATH:-$APPDIR/.venv}")
    SERVICE_SHORTNAME=$(ask "Service shortname (no 'gunicorn_' prefix)" "${SERVICE_SHORTNAME}")
    USE_TCP=$(ask "Use TCP (1) or Unix socket (0)" "${USE_TCP:-0}")
    if [[ "$USE_TCP" == "1" ]]; then
      PORT=$(ask "Port to bind Gunicorn to" "${PORT}")
      if ! is_port_free "$PORT"; then
        echo "Port $PORT appears to be in use. Pick another port." >&2
        exit 1
      fi
    else
      SOCKET_PATH=$(ask "Socket path" "${SOCKET_PATH:-/home/${DEPLOY_USER}/domains/${DOMAIN}/public_html/gunicorn.sock}")
    fi
  fi

  # Expand any placeholders (e.g. APPDIR may contain ${DEPLOY_USER} placeholders)
  APPDIR=$(eval echo "$APPDIR")
  VENV_PATH=$(eval echo "$VENV_PATH")
  SOCKET_PATH=$(eval echo "${SOCKET_PATH-}")
  SOCKET_PATH=$(eval echo "$SOCKET_PATH")
  PUBLIC_HTML=$(eval echo "${PUBLIC_HTML:-/home/${DEPLOY_USER}/domains/${DOMAIN}/public_html}")
  STATIC_DIR=$(eval echo "${STATIC_DIR:-${APPDIR}/static_assets}")

  # Validate socket directory, ownership and SELinux advice
  if [[ "${USE_TCP:-0}" != "1" ]]; then
    SOCKET_DIR=$(dirname "$SOCKET_PATH")
    if [[ ! -d "$SOCKET_DIR" ]]; then
      log "Socket directory $SOCKET_DIR does not exist. Creating."
      if [[ "$DRY_RUN" -eq 0 ]]; then
        mkdir -p "$SOCKET_DIR"
      fi
    fi
    validate_socket || true
    check_selinux || true
  fi

  STATIC_DIR=${STATIC_DIR:-${APPDIR}/static_assets}
  PUBLIC_HTML=${PUBLIC_HTML:-/home/${DEPLOY_USER}/domains/${DOMAIN}/public_html}
  LOG_DIR=${LOG_DIR:-${APPDIR}/logs}
  DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-ecatalogus.settings}

  mkdir -p "$LOG_DIR"
  LOG_FILE="$LOG_DIR/install_$(timestamp).log"

  {
    log "=== Install started: $(date) ==="
    log "APPDIR=$APPDIR"
    log "REPO_URL=$REPO_URL"

    start_gauge
    update_gauge 5 "Preparing application directory"

    if [[ ! -d "$APPDIR" || -z "$(ls -A "$APPDIR" 2>/dev/null)" ]]; then
      log "Application directory $APPDIR is missing or empty. Will clone repository."
      mkdir -p "$APPDIR"
      if [[ "$DRY_RUN" -eq 1 ]]; then
        log "DRY-RUN: would clone $REPO_URL@$GIT_BRANCH to $APPDIR"
        update_gauge 10 "(dry-run) clone"
      else
        ensure_ssh_known_host
        ensure_ssh_key "$REPO_URL"
        if ! try_git_clone "$REPO_URL" "$GIT_BRANCH" "$APPDIR"; then
          log "git clone failed. Checking for SSH key issues."
          print_git_ssh_help
          exit 1
        fi
        update_gauge 20 "Cloned repository"
      fi
    else
      log "App directory exists; checking git repository status."
      # If the directory exists but isn't a git repo, offer to back it up and clone fresh
      if [[ ! -d "$APPDIR/.git" ]]; then
        log "Directory $APPDIR exists but is not a git repository."
        if [[ "$DRY_RUN" -eq 1 ]]; then
          log "DRY-RUN: would move $APPDIR to ${APPDIR}.bak.", update_gauge 20 "(dry-run) backup and clone"
          update_gauge 20 "(dry-run) backup and clone"
        else
          DO_BACKUP=0
          if whiptail_ok; then
            if whiptail --title "Non-git directory" --yesno "Directory $APPDIR exists but is not a git repository. Move it to ${APPDIR}.bak.$(timestamp) and clone fresh from $REPO_URL ?" 12 70; then
                restore_tty
                DO_BACKUP=1
            else
                restore_tty
                DO_BACKUP=0
            fi
          else
              read -rp "Directory $APPDIR exists but is not a git repository. Move to backup and clone? [y/N]: " yn </dev/tty
            case "$yn" in
              [Yy]*) DO_BACKUP=1 ;;
              *) DO_BACKUP=0 ;;
            esac
          fi

          if [[ "$DO_BACKUP" -eq 1 ]]; then
            BACKUP_PATH="${APPDIR}.bak.$(timestamp)"
            log "Backing up $APPDIR -> $BACKUP_PATH"
            mv "$APPDIR" "$BACKUP_PATH" || { log "Failed to move $APPDIR to $BACKUP_PATH"; exit 1; }
            mkdir -p "$APPDIR"
            log "Cloning repository into $APPDIR"
            ensure_ssh_known_host
            ensure_ssh_key "$REPO_URL"
            if ! try_git_clone "$REPO_URL" "$GIT_BRANCH" "$APPDIR"; then
              log "git clone failed. Checking for SSH key issues."
              print_git_ssh_help
              exit 1
            fi
            update_gauge 30 "Cloned into fresh directory"
          else
            log "User chose not to backup/replace existing directory. Aborting."; exit 1
          fi
        fi
      else
        log "App directory is a git repository; fetching latest from git."
        cd "$APPDIR"
        if [[ "$DRY_RUN" -eq 1 ]]; then
          log "DRY-RUN: would fetch and reset to origin/$GIT_BRANCH"
          update_gauge 20 "(dry-run) update"
        else
          ensure_ssh_known_host
          if ! git fetch --all; then
            log "git fetch failed. Checking for SSH key issues."
            print_git_ssh_help
            exit 1
          fi
          git reset --hard "origin/$GIT_BRANCH"
          update_gauge 30 "Fetched latest"
        fi
      fi
    fi

    cd "$APPDIR"

    if [[ ! -d "$VENV_PATH" ]]; then
      log "Creating virtualenv at $VENV_PATH"
      if [[ "$DRY_RUN" -eq 1 ]]; then
        log "DRY-RUN: would create virtualenv at $VENV_PATH"
        update_gauge 35 "(dry-run) create venv"
      else
        python3.11 -m venv "$VENV_PATH"
        update_gauge 45 "Virtualenv created"
      fi
    fi

    # activate and install
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "DRY-RUN: would activate venv and install requirements"
      update_gauge 55 "(dry-run) install deps"
    else
      # shellcheck source=/dev/null
      source "$VENV_PATH/bin/activate"
      pip install --upgrade pip
      if [[ -f requirements.txt ]]; then
        pip install -r requirements.txt || true
      fi
      update_gauge 70 "Dependencies installed"
    fi

    # Preserve local files if any listed
    IFS=',' read -ra PRESERVE <<< "${PRESERVE_FILES-}"
    TMP_PRESERVE=$(mktemp -d)
    for f in "${PRESERVE[@]}"; do
      ftrim=$(echo "$f" | xargs)
      if [[ -n "$ftrim" && -f "$APPDIR/$ftrim" ]]; then
        mkdir -p "$TMP_PRESERVE/$(dirname "$ftrim")"
        cp -a "$APPDIR/$ftrim" "$TMP_PRESERVE/$ftrim"
      fi
    done

    # Run migrations and collectstatic
      # Source instance secrets if present (APPDIR/.env)
      if [[ -f "$APPDIR/.env" ]]; then
        # shellcheck source=/dev/null
        source "$APPDIR/.env"
        log "Sourced $APPDIR/.env"
      else
        ensure_app_env
      fi

      # Generate per-instance settings module and ensure DJANGO_SETTINGS_MODULE is set in .env
      write_settings_module

      # Ensure the DJANGO_SETTINGS_MODULE variable (generated/overwritten by write_settings_module)
      # is exported for manage.py commands
      export DJANGO_SETTINGS_MODULE="$(grep -E '^DJANGO_SETTINGS_MODULE=' "$APPDIR/.env" 2>/dev/null | cut -d'=' -f2-)"
      if [[ "$DRY_RUN" -eq 1 ]]; then
        log "DRY-RUN: would run makemigrations/migrate/collectstatic"
        update_gauge 85 "(dry-run) migrations & collectstatic"
      else
        update_gauge 80 "Running makemigrations"
        python manage.py makemigrations || true
        update_gauge 85 "Applying migrations"
        python manage.py migrate --noinput
        update_gauge 90 "Collecting static files"
        python manage.py collectstatic --noinput
        update_gauge 95 "Finalizing"
      fi

    # Restore preserved files (keep local config)
    if [[ -d "$TMP_PRESERVE" ]]; then
      cp -a "$TMP_PRESERVE/"* "$APPDIR/" 2>/dev/null || true
      rm -rf "$TMP_PRESERVE"
    fi

    # Create symlinks in public_html
    mkdir -p "$PUBLIC_HTML"
    ln -sf "$APPDIR/media" "$PUBLIC_HTML/media"
    ln -sf "$APPDIR/static_assets" "$PUBLIC_HTML/static"

    # Write back a copy of the config for future runs
    mkdir -p "$SCRIPT_DIR/config"
    OUT_CONF="$SCRIPT_DIR/config/${DOMAIN}.env"
    cat > "$OUT_CONF" <<EOF
DOMAIN=$DOMAIN
DEPLOY_USER=$DEPLOY_USER
REPO_URL=$REPO_URL
GIT_BRANCH=$GIT_BRANCH
APPDIR=$APPDIR
VENV_PATH=$VENV_PATH
SERVICE_SHORTNAME=$SERVICE_SHORTNAME
USE_TCP=$USE_TCP
PORT=$PORT
SOCKET_PATH=${SOCKET_PATH-}
STATIC_DIR=$STATIC_DIR
PUBLIC_HTML=$PUBLIC_HTML
LOG_DIR=$LOG_DIR
DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
PRESERVE_FILES=${PRESERVE_FILES-}
EOF

    log "Saved config to $OUT_CONF"

    # Prepare render variables and render service template into deploy/ for review
    mkdir -p "$SCRIPT_DIR/../deploy"
    SERVICE_OUT="$SCRIPT_DIR/../deploy/gunicorn_${SERVICE_SHORTNAME}.service"
    # choose bind
    if [[ "${USE_TCP:-0}" == "1" ]]; then
      BIND="--bind 0.0.0.0:${PORT}"
    else
      BIND="--bind unix:${SOCKET_PATH}"
    fi
    ENV_FILE_PATH="${APPDIR}/.env"
    render_service "$SERVICE_OUT" && log "Wrote service template to $SERVICE_OUT"

    if [[ "$INSTALL_UNIT" -eq 1 ]]; then
      TARGET_UNIT="/etc/systemd/system/gunicorn_${SERVICE_SHORTNAME}.service"
      if [[ "$DRY_RUN" -eq 1 ]]; then
        log "DRY-RUN: would install $SERVICE_OUT to $TARGET_UNIT and enable service"
        update_gauge 98 "(dry-run) render/install unit"
        stop_gauge
      else
        update_gauge 98 "Installing unit (may require sudo)"
        if [[ $EUID -eq 0 ]]; then
          cp -f "$SERVICE_OUT" "$TARGET_UNIT"
          systemctl daemon-reload
          systemctl enable --now "gunicorn_${SERVICE_SHORTNAME}.service" || true
          log "Installed and enabled $TARGET_UNIT as root"
        else
          if sudo -n true 2>/dev/null; then
            sudo cp -f "$SERVICE_OUT" "$TARGET_UNIT"
            sudo systemctl daemon-reload
            sudo systemctl enable --now "gunicorn_${SERVICE_SHORTNAME}.service" || true
            log "Installed and enabled $TARGET_UNIT via sudo"
          else
            log "--install-unit requested but no sudo/root available. Generated unit is at $SERVICE_OUT"
          fi
        fi
        stop_gauge
      fi
    fi

    log "=== Install finished: $(date) ==="
  } 2>&1 | tee "$LOG_FILE"

  echo "Install complete. Review $LOG_FILE and $OUT_CONF"
  echo "To install the systemd unit as root, copy deploy/gunicorn_${SERVICE_SHORTNAME}.service to /etc/systemd/system/ and run:" \
       "sudo systemctl daemon-reload && sudo systemctl enable --now gunicorn_${SERVICE_SHORTNAME}.service"
}

main "${1-}"
