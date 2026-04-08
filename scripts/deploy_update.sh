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

usage() {
  cat <<EOF
Usage: $(basename "$0") [config.env] [--dry-run] [--non-interactive] [--force-reset]
EOF
}

timestamp() { date +%Y%m%d-%H%M%S; }
log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
warn() { log "WARNING: $*"; }
die() { log "ERROR: $*"; exit 1; }

cleanup() {
  if [[ -n "$TMP_PRESERVE" && -d "$TMP_PRESERVE" ]]; then
    rm -rf "$TMP_PRESERVE"
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
  DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-ecatalogus.settings}
  SERVICE_SHORTNAME=${SERVICE_SHORTNAME:-}
  PRESERVE_FILES=${PRESERVE_FILES:-}

  if [[ "$REPO_URL" =~ ^https://github.com/[^[:space:]]+$ && "$REPO_URL" != *.git ]]; then
    REPO_URL="${REPO_URL}.git"
  fi

  APPDIR=$(expand_template_value "$APPDIR")
  VENV_PATH=$(expand_template_value "$VENV_PATH")
  PUBLIC_HTML=$(expand_template_value "$PUBLIC_HTML")
  STATIC_DIR=$(expand_template_value "$STATIC_DIR")
  LOG_DIR=$(expand_template_value "$LOG_DIR")
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
    [[ "$path" == "$item" ]] && return 0
  done
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
    if path_is_preserved "$line" || [[ "$line" == .env || "$line" == .env.* ]]; then
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
  set -a
  # shellcheck source=/dev/null
  source "$env_file"
  set +a
  export DJANGO_SETTINGS_MODULE
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
  load_runtime_env

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would install dependencies"
  elif [[ -f "${APPDIR}/requirements.txt" ]]; then
    "${VENV_PATH}/bin/python" -m pip install --upgrade pip
    "${VENV_PATH}/bin/pip" install -r "${APPDIR}/requirements.txt"
  else
    warn "requirements.txt not found in ${APPDIR}; skipping dependency installation"
  fi

  validate_settings_module
  run_manage check
  run_manage migrate --noinput
  run_manage collectstatic --noinput
  restart_service

  log "Deploy finished successfully"
  log "Deploy log: ${LOG_FILE}"
}

main "$@"
