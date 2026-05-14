#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_ENV="${SCRIPT_DIR}/config/example.env"

DRY_RUN=0
NON_INTERACTIVE=0
FORCE_RESET=0
CFG_ARG=""
CONFIG_SOURCE=""
LOG_FILE=""
TMP_PRESERVE=""
TMP_RENDERED_SETTINGS=""
MEDIA_DIR=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [config.env] [--dry-run] [--non-interactive] [--force-reset]
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

cleanup() {
  if [[ -n "$TMP_PRESERVE" && -d "$TMP_PRESERVE" ]]; then
    rm -rf "$TMP_PRESERVE"
  fi
  if [[ -n "$TMP_RENDERED_SETTINGS" && -d "$TMP_RENDERED_SETTINGS" ]]; then
    local settings_target=""
    local alias_target=""
    if [[ -f "${TMP_RENDERED_SETTINGS}/settings_file_target" ]]; then
      settings_target=$(cat "${TMP_RENDERED_SETTINGS}/settings_file_target")
    fi
    if [[ -f "${TMP_RENDERED_SETTINGS}/alias_file_target" ]]; then
      alias_target=$(cat "${TMP_RENDERED_SETTINGS}/alias_file_target")
    fi

    if [[ -f "${TMP_RENDERED_SETTINGS}/restore_settings_file" ]]; then
      cp "${TMP_RENDERED_SETTINGS}/restore_settings_file" "$settings_target"
    elif [[ -n "$settings_target" ]]; then
      rm -f "$settings_target"
    fi

    if [[ -f "${TMP_RENDERED_SETTINGS}/restore_alias_file" ]]; then
      cp "${TMP_RENDERED_SETTINGS}/restore_alias_file" "$alias_target"
    elif [[ -n "$alias_target" ]]; then
      rm -f "$alias_target"
    fi

    rm -rf "$TMP_RENDERED_SETTINGS"
  fi
}

trap cleanup EXIT

parse_args() {
  while (($#)); do
    case "$1" in
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --non-interactive)
        NON_INTERACTIVE=1
        shift
        ;;
      --force-reset)
        FORCE_RESET=1
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
          shift
        else
          die "Unexpected extra argument: $1"
        fi
        ;;
    esac
  done
}

load_config() {
  CONFIG_SOURCE=${CFG_ARG:-$DEFAULT_ENV}
  [[ -f "$CONFIG_SOURCE" ]] || die "Config file not found: $CONFIG_SOURCE"
  # shellcheck source=/dev/null
  source "$CONFIG_SOURCE"
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

resolve_config() {
  DOMAIN=${DOMAIN:-}
  DEPLOY_USER=${DEPLOY_USER:-}
  REPO_URL=${REPO_URL:-}
  GIT_BRANCH=${GIT_BRANCH:-main}
  APPDIR=${APPDIR:-/home/${DEPLOY_USER}/domains/${DOMAIN}/ecatalogus}
  VENV_PATH=${VENV_PATH:-${APPDIR}/.venv}
  PUBLIC_HTML=${PUBLIC_HTML:-/home/${DEPLOY_USER}/domains/${DOMAIN}/public_html}
  STATIC_DIR=${STATIC_DIR:-${APPDIR}/staticfiles}
  LOG_DIR=${LOG_DIR:-${APPDIR}/logs}
  DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-ecatalogus.settings}
  SERVICE_SHORTNAME=${SERVICE_SHORTNAME:-}
  PRESERVE_FILES=${PRESERVE_FILES:-}
  MEDIA_DIR=${MEDIA_DIR:-}

  if [[ "$REPO_URL" =~ ^https://github.com/[^[:space:]]+$ && "$REPO_URL" != *.git ]]; then
    REPO_URL="${REPO_URL}.git"
  fi

  APPDIR=$(expand_template_value "$APPDIR")
  VENV_PATH=$(expand_template_value "$VENV_PATH")
  PUBLIC_HTML=$(expand_template_value "$PUBLIC_HTML")
  STATIC_DIR=$(expand_template_value "$STATIC_DIR")
  LOG_DIR=$(expand_template_value "$LOG_DIR")
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

validate_config() {
  local missing=()
  local name
  for name in DOMAIN DEPLOY_USER REPO_URL GIT_BRANCH APPDIR VENV_PATH LOG_DIR SERVICE_SHORTNAME DJANGO_SETTINGS_MODULE; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
  done
  if ((${#missing[@]})); then
    die "Missing required config values: ${missing[*]}"
  fi
  [[ -d "$APPDIR/.git" ]] || die "APPDIR is not a git checkout: $APPDIR"
  [[ -x "$VENV_PATH/bin/python" ]] || die "Virtualenv python not found: ${VENV_PATH}/bin/python"
}

prepare_logging() {
  mkdir -p "$LOG_DIR"
  LOG_FILE="${LOG_DIR}/deploy_$(timestamp).log"
  exec > >(tee -a "$LOG_FILE") 2>&1
  log "Using configuration from ${CONFIG_SOURCE}"
}

build_preserve_paths() {
  PRESERVE_PATHS=()
  local item
  local -a raw_paths=()
  if [[ -n "$PRESERVE_FILES" ]]; then
    IFS=',' read -r -a raw_paths <<< "$PRESERVE_FILES"
  fi
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
    [[ "$path" == "$item" ]] && return 0
  done
  return 1
}

path_is_managed_generated() {
  local path=$1
  local module_name="${DJANGO_SETTINGS_MODULE##*.}"

  case "$path" in
    ecatalogus/settings.py)
      return 0
      ;;
    "ecatalogus/${module_name}.py")
      return 0
      ;;
    "deploy/nginx_${SERVICE_SHORTNAME}_custom3.conf")
      return 0
      ;;
    "deploy/gunicorn_${SERVICE_SHORTNAME}.service")
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
    die "Repository has unexpected local changes. Resolve them or rerun with --force-reset to discard them."
  fi
}

load_runtime_env() {
  local env_file="${APPDIR}/.env"
  [[ -f "$env_file" ]] || die "Runtime env file is missing: ${env_file}"
  local configured_settings_module="$DJANGO_SETTINGS_MODULE"
  set -a
  # shellcheck source=/dev/null
  source "$env_file"
  set +a
  if [[ "${DJANGO_SETTINGS_MODULE:-}" != "$configured_settings_module" ]]; then
    warn "Runtime env DJANGO_SETTINGS_MODULE (${DJANGO_SETTINGS_MODULE:-unset}) differs from deploy config (${configured_settings_module}); using deploy config."
    DJANGO_SETTINGS_MODULE="$configured_settings_module"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      upsert_env_value "$env_file" "DJANGO_SETTINGS_MODULE" "${DJANGO_SETTINGS_MODULE}"
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$env_file" 2>/dev/null || true
      chmod 600 "$env_file"
    fi
  fi
  export DJANGO_SETTINGS_MODULE
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
    TMP_RENDERED_SETTINGS=${TMP_RENDERED_SETTINGS:-$(mktemp -d)}
    printf '%s' "$settings_file" > "${TMP_RENDERED_SETTINGS}/settings_file_target"
    printf '%s' "$alias_file" > "${TMP_RENDERED_SETTINGS}/alias_file_target"
    if [[ -f "$settings_file" && ! -f "${TMP_RENDERED_SETTINGS}/restore_settings_file" ]]; then
      cp "$settings_file" "${TMP_RENDERED_SETTINGS}/restore_settings_file"
    fi
    if [[ -f "$alias_file" && ! -f "${TMP_RENDERED_SETTINGS}/restore_alias_file" ]]; then
      cp "$alias_file" "${TMP_RENDERED_SETTINGS}/restore_alias_file"
    fi
  fi

  mkdir -p "$settings_dir"
  cat > "$settings_file" <<EOF
"""Managed by scripts/deploy_update.sh for ${DOMAIN}."""

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

validate_settings_module() {
  local venv_python="${VENV_PATH}/bin/python"
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

run_manage() {
  local venv_python="${VENV_PATH}/bin/python"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would run manage.py $*"
    return 0
  fi
  (
    cd "$APPDIR"
    "$venv_python" manage.py "$@"
  )
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

ensure_parent_traversal() {
  local target_path=$1
  local current_path

  current_path=$(dirname "$target_path")
  while [[ -n "$current_path" && "$current_path" != "/" ]]; do
    chmod o+x "$current_path" 2>/dev/null || true
    current_path=$(dirname "$current_path")
  done
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

  mkdir -p "$PUBLIC_HTML"
  mkdir -p "$MEDIA_DIR" "$STATIC_DIR"
  ln -sfn "$MEDIA_DIR" "$PUBLIC_HTML/media"
  ln -sfn "$STATIC_DIR" "$PUBLIC_HTML/static"
  chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "$MEDIA_DIR" "$STATIC_DIR" 2>/dev/null || true
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "$PUBLIC_HTML" 2>/dev/null || true
  chown -h "${DEPLOY_USER}:${DEPLOY_USER}" "$PUBLIC_HTML/media" "$PUBLIC_HTML/static" 2>/dev/null || true
  chmod 755 "$PUBLIC_HTML" 2>/dev/null || true
  find "$MEDIA_DIR" "$STATIC_DIR" -type d -exec chmod 755 {} + 2>/dev/null || true
  find "$MEDIA_DIR" "$STATIC_DIR" -type f -exec chmod 644 {} + 2>/dev/null || true
  ensure_parent_traversal "$STATIC_DIR"
  ensure_parent_traversal "$MEDIA_DIR"
  ensure_parent_traversal "$PUBLIC_HTML"
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

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would install DirectAdmin CUSTOM3 snippet for ${DOMAIN}"
    return 0
  fi

  if [[ $EUID -ne 0 ]]; then
    log "Not running as root — saved DirectAdmin nginx snippet to ${snippet_src}. If the site returns 403 for /static or /media, install it manually with: sudo bash scripts/install_directadmin_custom3.sh ${CONFIG_SOURCE}"
    return 0
  fi

  local da_user_dir="/usr/local/directadmin/data/users/${DEPLOY_USER}/domains"
  local target_file="${da_user_dir}/${DOMAIN}.conf"
  local begin_marker="# BEGIN COPILOT_CUSTOM3 ${SERVICE_SHORTNAME}"
  local end_marker="# END COPILOT_CUSTOM3 ${SERVICE_SHORTNAME}"
  local temp_file

  if [[ ! -d "$da_user_dir" ]]; then
    warn "DirectAdmin user domains directory not found: ${da_user_dir}; not installing snippet automatically"
    return 0
  fi

  mkdir -p "$da_user_dir"
  if [[ -f "$target_file" ]]; then
    cp -a "$target_file" "${target_file}.bak_$(timestamp)" || true
  fi

  temp_file=$(mktemp)
  if [[ -f "$target_file" ]]; then
    awk -v begin="$begin_marker" -v end="$end_marker" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$target_file" > "$temp_file"
  fi

  {
    cat "$temp_file"
    printf "\n%s\n" "$begin_marker"
    cat "$snippet_src"
    printf "%s\n" "$end_marker"
  } > "$target_file"
  rm -f "$temp_file"

  log "Installed DirectAdmin CUSTOM3 snippet into ${target_file}"

  if [[ -x "/usr/local/directadmin/custombuild/build" ]]; then
    /usr/local/directadmin/custombuild/build rewrite_confs || warn "custombuild rewrite_confs failed"
  elif [[ -x "/usr/local/directadmin/scripts/rewrite_confs.sh" ]]; then
    /usr/local/directadmin/scripts/rewrite_confs.sh || warn "rewrite_confs.sh failed"
  else
    warn "Could not find DirectAdmin build script; run rewrite_confs manually"
  fi
}

restart_service() {
  local svc="gunicorn_${SERVICE_SHORTNAME}.service"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would restart ${svc}"
    return 0
  fi
  if [[ $EUID -eq 0 ]]; then
    systemctl restart "$svc"
    return 0
  fi
  if sudo -n true 2>/dev/null; then
    sudo systemctl restart "$svc"
    return 0
  fi
  warn "Could not restart ${svc} automatically. Restart it manually to apply the new code."
}

main() {
  parse_args "$@"
  load_config
  resolve_config
  validate_config
  prepare_logging

  log "=== Deploy started ==="
  cd "$APPDIR"

  local origin_url
  origin_url=$(git remote get-url origin)
  if [[ "$(canonical_repo_url "$origin_url")" != "$(canonical_repo_url "$REPO_URL")" ]]; then
    die "Configured REPO_URL (${REPO_URL}) does not match origin remote (${origin_url})."
  fi

  build_preserve_paths
  guard_unexpected_git_changes
  backup_preserved_files

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would fetch origin ${GIT_BRANCH} and reset working tree"
  else
    if [[ "$FORCE_RESET" -eq 1 ]]; then
      warn "--force-reset enabled; discarding unpreserved local changes before updating from origin"
    fi
    git fetch --prune origin "$GIT_BRANCH"
    git checkout -B "$GIT_BRANCH" "origin/${GIT_BRANCH}"
    git reset --hard "origin/${GIT_BRANCH}"
  fi

  restore_preserved_files
  render_instance_settings_files
  load_runtime_env

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would install dependencies"
  elif [[ -f "${APPDIR}/requirements.txt" ]]; then
    "${VENV_PATH}/bin/python" -m pip install --upgrade pip
    "${VENV_PATH}/bin/pip" install -r "${APPDIR}/requirements.txt"
  else
    warn "requirements.txt not found in ${APPDIR}; skipping dependency installation"
  fi

  log "------------------------------ run_download_libs ------------------------------"
  run_download_libs
  log "------------------------------ validate_settings_module ------------------------------"
  validate_settings_module
  log "------------------------------ check ------------------------------"
  run_manage check
  #migrations are now synchronized in repo
  #run_manage makemigrations indexerapp --noinput
  log "------------------------------ migrate ------------------------------"
  run_manage migrate --noinput
  log "------------------------------ collectstatic ------------------------------"
  run_manage collectstatic --noinput
  log "------------------------------ link_public_assets ------------------------------"
  link_public_assets
  log "------------------------------ render_nginx_snippet ------------------------------"
  render_nginx_snippet
  log "------------------------------ install_directadmin_snippet ------------------------------"

  install_directadmin_snippet
  restart_service

  log "Deploy finished successfully"
  log "Deploy log: ${LOG_FILE}"
}

main "$@"
