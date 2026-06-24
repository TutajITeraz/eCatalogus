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
ENV_FILE=""

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
  STATIC_DIR=${STATIC_DIR:-${APPDIR}/static_assets}
  LOG_DIR=${LOG_DIR:-${APPDIR}/logs}
  SERVICE_SHORTNAME=${SERVICE_SHORTNAME:-}
  INSTANCE_SLUG=${INSTANCE_SLUG:-}
  ETL_USE_CELERY=${ETL_USE_CELERY:-1}
  PRESERVE_FILES=${PRESERVE_FILES:-}
  MEDIA_DIR=${MEDIA_DIR:-}

  if [[ -z "${DJANGO_SETTINGS_MODULE:-}" ]]; then
    if [[ -n "$SERVICE_SHORTNAME" ]]; then
      DJANGO_SETTINGS_MODULE="ecatalogus.settings_${SERVICE_SHORTNAME}"
    else
      DJANGO_SETTINGS_MODULE=""
    fi
  fi

  if [[ -z "$INSTANCE_SLUG" && "$DJANGO_SETTINGS_MODULE" == ecatalogus.settings_* ]]; then
    INSTANCE_SLUG="${DJANGO_SETTINGS_MODULE##*.settings_}"
  fi

  if [[ -z "$SERVICE_SHORTNAME" && -n "$INSTANCE_SLUG" ]]; then
    SERVICE_SHORTNAME="$INSTANCE_SLUG"
  fi

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

ensure_runtime_log_files() {
  local log_dir="$LOG_DIR"
  local django_error_log="${log_dir}/error.log"
  local gunicorn_log="${log_dir}/gunicorn.log"
  local celery_log="${log_dir}/celery.log"

  mkdir -p "$log_dir"
  touch "$django_error_log" "$gunicorn_log" "$celery_log"
  chown "${DEPLOY_USER}:${DEPLOY_USER}" "$log_dir" "$django_error_log" "$gunicorn_log" "$celery_log" 2>/dev/null || true
  chmod 755 "$log_dir" 2>/dev/null || true
  chmod 640 "$django_error_log" "$gunicorn_log" "$celery_log" 2>/dev/null || true
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
  local legacy_domain_config="scripts/config/${DOMAIN}.env"
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
    "deploy/celery_${SERVICE_SHORTNAME}.service")
      return 0
      ;;
    "$legacy_domain_config")
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
  ENV_FILE="${APPDIR}/.env"
  [[ -f "$ENV_FILE" ]] || die "Runtime env file is missing: ${ENV_FILE}"
  local configured_settings_module="$DJANGO_SETTINGS_MODULE"
  local configured_instance_slug="${INSTANCE_SLUG:-}"
  local configured_service_shortname="${SERVICE_SHORTNAME:-}"
  local configured_etl_use_celery="${ETL_USE_CELERY:-1}"
  local expected_instance_slug="$configured_instance_slug"

  if [[ -z "$expected_instance_slug" && "$configured_settings_module" == ecatalogus.settings_* ]]; then
    expected_instance_slug="${configured_settings_module##*.settings_}"
  fi
  if [[ -z "$expected_instance_slug" && -n "$configured_service_shortname" ]]; then
    expected_instance_slug="$configured_service_shortname"
  fi

  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a

  if [[ "${DJANGO_SETTINGS_MODULE:-}" != "$configured_settings_module" ]]; then
    warn "Runtime env DJANGO_SETTINGS_MODULE (${DJANGO_SETTINGS_MODULE:-unset}) differs from deploy config (${configured_settings_module}); using deploy config."
    DJANGO_SETTINGS_MODULE="$configured_settings_module"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      upsert_env_value "$ENV_FILE" "DJANGO_SETTINGS_MODULE" "${DJANGO_SETTINGS_MODULE}"
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
      chmod 600 "$ENV_FILE"
    fi
  fi

  if [[ -n "$configured_service_shortname" && "${SERVICE_SHORTNAME:-}" != "$configured_service_shortname" ]]; then
    warn "Runtime env SERVICE_SHORTNAME (${SERVICE_SHORTNAME:-unset}) differs from deploy config (${configured_service_shortname}); using deploy config."
    SERVICE_SHORTNAME="$configured_service_shortname"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      upsert_env_value "$ENV_FILE" "SERVICE_SHORTNAME" "${SERVICE_SHORTNAME}"
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
      chmod 600 "$ENV_FILE"
    fi
  fi

  if [[ -n "$expected_instance_slug" && "${INSTANCE_SLUG:-}" != "$expected_instance_slug" ]]; then
    warn "Runtime env INSTANCE_SLUG (${INSTANCE_SLUG:-unset}) differs from deploy config (${expected_instance_slug}); using deploy config."
    INSTANCE_SLUG="$expected_instance_slug"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      upsert_env_value "$ENV_FILE" "INSTANCE_SLUG" "${INSTANCE_SLUG}"
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
      chmod 600 "$ENV_FILE"
    fi
  fi

  if [[ "${ETL_USE_CELERY:-1}" != "$configured_etl_use_celery" ]]; then
    warn "Runtime env ETL_USE_CELERY (${ETL_USE_CELERY:-unset}) differs from deploy config (${configured_etl_use_celery}); using deploy config."
    ETL_USE_CELERY="$configured_etl_use_celery"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      upsert_env_value "$ENV_FILE" "ETL_USE_CELERY" "${ETL_USE_CELERY}"
      chown "${DEPLOY_USER}:${DEPLOY_USER}" "$ENV_FILE" 2>/dev/null || true
      chmod 600 "$ENV_FILE"
    fi
  fi

  export DJANGO_SETTINGS_MODULE
  export INSTANCE_SLUG
  export SERVICE_SHORTNAME
  export ETL_USE_CELERY
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

cleanup_legacy_static_artifacts() {
  local nested_static_dir="${STATIC_DIR}/static_assets"
  local legacy_staticfiles_dir="${APPDIR}/staticfiles"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ -e "$nested_static_dir" || -L "$nested_static_dir" ]]; then
      log "DRY-RUN: would remove legacy nested static artifact ${nested_static_dir}"
    fi
    if [[ -d "$legacy_staticfiles_dir" ]]; then
      log "DRY-RUN: would remove legacy static output directory ${legacy_staticfiles_dir}"
    fi
    return 0
  fi

  if [[ -e "$nested_static_dir" || -L "$nested_static_dir" ]]; then
    rm -rf "$nested_static_dir"
    log "Removed legacy nested static artifact ${nested_static_dir}"
  fi

  if [[ -d "$legacy_staticfiles_dir" ]]; then
    rm -rf "$legacy_staticfiles_dir"
    log "Removed legacy static output directory ${legacy_staticfiles_dir}"
  fi
}

recreate_symlink() {
  local target_path=$1
  local link_path=$2

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would recreate symlink ${link_path} -> ${target_path}"
    return 0
  fi

  rm -rf "$link_path"
  ln -s "$target_path" "$link_path"
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
  recreate_symlink "$MEDIA_DIR" "$PUBLIC_HTML/media"
  recreate_symlink "$STATIC_DIR" "$PUBLIC_HTML/static"
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

render_service() {
  local service_out="${SCRIPT_DIR}/../deploy/gunicorn_${SERVICE_SHORTNAME}.service"
  local template="${SCRIPT_DIR}/../deploy/gunicorn.service.template"
  local bind_arg=""
  local django_error_log="${LOG_DIR}/error.log"
  local gunicorn_log="${LOG_DIR}/gunicorn.log"
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
  ensure_runtime_log_files

  local chosen_gunicorn path_val
  if [[ -x "${VENV_PATH}/bin/gunicorn" ]]; then
    chosen_gunicorn="${VENV_PATH}/bin/gunicorn"
    path_val="${VENV_PATH}/bin"
  else
    die "Gunicorn binary not found in ${VENV_PATH}/bin. Install dependencies into the virtualenv before rendering the service."
  fi

  local py_path
  py_path="${APPDIR}"
  if [[ -x "${VENV_PATH}/bin/python" ]]; then
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
      -e "s|{LOG_DIR}|${LOG_DIR}|g" \
      -e "s|{ERROR_LOG_FILE}|${django_error_log}|g" \
      -e "s|{GUNICORN_LOG_FILE}|${gunicorn_log}|g" \
      -e "s|{PYTHONPATH}|${py_path}|g" \
      "$template" > "$service_out"
  log "Rendered systemd unit to ${service_out}"
}

render_celery_service() {
  local service_out="${SCRIPT_DIR}/../deploy/celery_${SERVICE_SHORTNAME}.service"
  local template="${SCRIPT_DIR}/../deploy/celery.service.template"
  local celery_queue="etl_${SERVICE_SHORTNAME}"
  local django_error_log="${LOG_DIR}/error.log"
  local celery_log="${LOG_DIR}/celery.log"
  [[ -f "$template" ]] || die "Service template not found: ${template}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would render Celery systemd unit to ${service_out}"
    return 0
  fi
  mkdir -p "${SCRIPT_DIR}/../deploy"
  ensure_runtime_log_files

  local chosen_celery path_val
  if [[ -x "${VENV_PATH}/bin/celery" ]]; then
    chosen_celery="${VENV_PATH}/bin/celery"
    path_val="${VENV_PATH}/bin"
  else
    die "Celery binary not found in ${VENV_PATH}/bin. Install dependencies into the virtualenv before rendering the service."
  fi

  local py_path
  py_path="${APPDIR}"
  if [[ -x "${VENV_PATH}/bin/python" ]]; then
    local venv_site
    venv_site=$("${VENV_PATH}/bin/python" -c 'import site, sys; s=site.getsitepackages(); print(s[0] if s else "")' 2>/dev/null || true)
    if [[ -n "$venv_site" ]]; then
      py_path="${APPDIR}:$venv_site"
    fi
  fi

  sed -e "s|{SERVICE_SHORTNAME}|${SERVICE_SHORTNAME}|g" \
      -e "s|{APPDIR}|${APPDIR}|g" \
      -e "s|{DJANGO_SETTINGS_MODULE}|${DJANGO_SETTINGS_MODULE}|g" \
      -e "s|{ENV_FILE}|${ENV_FILE}|g" \
      -e "s|{DEPLOY_USER}|${DEPLOY_USER}|g" \
      -e "s|{CELERY_QUEUE}|${celery_queue}|g" \
      -e "s|{CELERY_BIN}|${chosen_celery}|g" \
      -e "s|{PATH}|${path_val}|g" \
      -e "s|{LOG_DIR}|${LOG_DIR}|g" \
      -e "s|{ERROR_LOG_FILE}|${django_error_log}|g" \
      -e "s|{CELERY_LOG_FILE}|${celery_log}|g" \
      -e "s|{PYTHONPATH}|${py_path}|g" \
      "$template" > "$service_out"
  log "Rendered Celery systemd unit to ${service_out}"
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
  local celery_svc="celery_${SERVICE_SHORTNAME}.service"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would restart ${svc} and ${celery_svc}"
    return 0
  fi

  local restart_cmd=""
  if [[ $EUID -eq 0 ]]; then
    restart_cmd="systemctl"
  elif sudo -n true 2>/dev/null; then
    restart_cmd="sudo systemctl"
  else
    warn "Could not restart ${svc} automatically. Restart it manually to apply the new code."
    warn "Could not restart ${celery_svc} automatically. Restart it manually if async ETL is enabled."
    return 0
  fi

  ${restart_cmd} restart "$svc"
  if ${restart_cmd} list-unit-files "$celery_svc" --no-legend >/dev/null 2>&1; then
    ${restart_cmd} restart "$celery_svc"
  else
    warn "Celery unit ${celery_svc} is not installed; async ETL will continue to fall back to direct execution until it is installed."
  fi
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
  log "------------------------------ cleanup_legacy_static_artifacts ------------------------------"
  cleanup_legacy_static_artifacts
  log "------------------------------ collectstatic ------------------------------"
  run_manage collectstatic --noinput
  log "------------------------------ link_public_assets ------------------------------"
  link_public_assets
  log "------------------------------ render_service ------------------------------"
  render_service
  log "------------------------------ render_celery_service ------------------------------"
  render_celery_service
  log "------------------------------ render_nginx_snippet ------------------------------"
  render_nginx_snippet
  log "------------------------------ install_directadmin_snippet ------------------------------"

  install_directadmin_snippet
  restart_service

  log "Deploy finished successfully"
  log "Deploy log: ${LOG_FILE}"
}

main "$@"
