#!/usr/bin/env bash
set -euo pipefail

# deploy_update.sh
# Pull latest code from git, preserve local config files, run migrations, collectstatic and restart service.

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# parse args: optional config file and flags
DRY_RUN=0
CFG=
while (( "$#" )); do
  case "$1" in
    --dry-run)
      DRY_RUN=1; shift ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [config.env] [--dry-run]
  Runs pull/reset from git, preserves local files, installs requirements,
  runs migrations and collectstatic, then restarts the service.

Examples:
  # Deploy using per-domain config
  ./$(basename "$0") scripts/config/ecatalogus.ispan.pl.env

  # Dry-run
  ./$(basename "$0") scripts/config/ecatalogus.ispan.pl.env --dry-run
EOF
      exit 0 ;;
    *)
      if [[ -z "$CFG" ]]; then CFG=$1; shift; else break; fi ;;
  esac
done

CFG=${CFG:-$SCRIPT_DIR/config/example.env}

if [[ -f "$CFG" ]]; then
  # shellcheck source=/dev/null
  source "$CFG"
else
  echo "Config file $CFG not found." >&2
  exit 1
fi

timestamp() { date +%Y%m%d-%H%M%S; }
log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

LOG_DIR=${LOG_DIR:-${APPDIR}/logs}
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy_$(timestamp).log"

# whiptail/gauge helpers for deploy
whiptail_ok() { command -v whiptail >/dev/null 2>&1; }
start_gauge() {
  if whiptail_ok; then
    GAUGE_PIPE=$(mktemp -u)
    mkfifo "$GAUGE_PIPE"
    whiptail --title "Deploy" --gauge "Starting..." 8 70 0 < "$GAUGE_PIPE" &
    GAUGE_PID=$!
    exec 3> "$GAUGE_PIPE"
  fi
}

# Validate socket ownership and permissions, attempt to fix when possible
validate_socket() {
  if [[ "${USE_TCP:-0}" == "1" ]]; then
    return 0
  fi
  local sock=${SOCKET_PATH:-$SOCKET_PATH}
  local sdir
  sdir=$(dirname "$sock")
  if [[ ! -d "$sdir" ]]; then
    log "Socket directory $sdir does not exist. Creating."
    if [[ "$DRY_RUN" -eq 0 ]]; then
      mkdir -p "$sdir"
    fi
  fi
  if [[ "$DRY_RUN" -eq 0 ]]; then
    chown "${DEPLOY_USER}:${DEPLOY_USER}" "$sdir" 2>/dev/null || true
    chmod 755 "$sdir" 2>/dev/null || true
  else
    log "DRY-RUN: would chown/chmod $sdir"
  fi

  if [[ -e "$sock" ]]; then
    if [[ -S "$sock" ]]; then
      owner=$(stat -c '%U' "$sock" 2>/dev/null || stat -f '%Su' "$sock" 2>/dev/null || true)
      if [[ "$owner" != "${DEPLOY_USER}" ]]; then
        log "Socket $sock owner is $owner, expected ${DEPLOY_USER}. Attempting fix."
        if [[ "$DRY_RUN" -eq 0 ]]; then
          chown ${DEPLOY_USER}:${DEPLOY_USER} "$sock" 2>/dev/null || true
          chmod 660 "$sock" 2>/dev/null || true
        fi
      fi
    else
      log "Warning: $sock exists but is not a socket. Backing up and removing."
      if [[ "$DRY_RUN" -eq 0 ]]; then
        mv "$sock" "${sock}.bak.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
      fi
    fi
  fi
}

# SELinux advisory
check_selinux() {
  if command -v getenforce >/dev/null 2>&1; then
    se=$(getenforce 2>/dev/null || true)
    if [[ "$se" == "Enforcing" ]]; then
      log "SELinux Enforcing: ensure correct contexts for socket and static/media directories."
    fi
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

{
  log "=== Deploy started: $(date) ==="
  log "APPDIR=$APPDIR"
  cd "$APPDIR"

  # Preserve files
  # Source instance secrets if present (APPDIR/.env)
  if [[ -f "$APPDIR/.env" ]]; then
    # shellcheck source=/dev/null
    source "$APPDIR/.env"
    log "Sourced $APPDIR/.env"
  else
    log "Warning: $APPDIR/.env not found. Deploy will continue but Django manage commands may fail without DB credentials."
  fi
 
  # Preserve files
  IFS=',' read -ra PRESERVE <<< "${PRESERVE_FILES-}"
  TMP_PRESERVE=$(mktemp -d)
  for f in "${PRESERVE[@]}"; do
    ftrim=$(echo "$f" | xargs)
    if [[ -n "$ftrim" && -f "$APPDIR/$ftrim" ]]; then
      mkdir -p "$TMP_PRESERVE/$(dirname "$ftrim")"
      cp -a "$APPDIR/$ftrim" "$TMP_PRESERVE/$ftrim"
    fi
  done

  # Update from git
  start_gauge
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would fetch, checkout and reset branch ${GIT_BRANCH:-main}"
    update_gauge 20 "(dry-run) git fetch"
  else
    git fetch --all --prune
    BRANCH_TO_RESET="${GIT_BRANCH:-main}"
    git checkout "$BRANCH_TO_RESET" || true
    git reset --hard "origin/${BRANCH_TO_RESET}"
    update_gauge 30 "Updated code"
  fi

  # Restore preserved files
  if [[ -d "$TMP_PRESERVE" ]]; then
    cp -a "$TMP_PRESERVE/"* "$APPDIR/" 2>/dev/null || true
    rm -rf "$TMP_PRESERVE"
  fi

  # activate virtualenv and run maintenance
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would activate venv, install requirements, run migrations and collectstatic"
    update_gauge 60 "(dry-run) maintenance"
  else
    # shellcheck source=/dev/null
    source "${VENV_PATH:-$APPDIR/.venv}/bin/activate"
    if [[ -f requirements.txt ]]; then
      pip install -r requirements.txt || true
    fi
    update_gauge 60 "Installing dependencies"
    export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE-ecatalogus.settings}"
    python manage.py makemigrations || true
    update_gauge 75 "Applying migrations"
    python manage.py migrate --noinput
    update_gauge 85 "Collecting static files"
    python manage.py collectstatic --noinput
    update_gauge 95 "Finishing"
  fi

  # restart service (gunicorn_{SERVICE_SHORTNAME}.service)
  svc="gunicorn_${SERVICE_SHORTNAME}.service"
  # run validations: socket ownership/permissions and SELinux advisory
  validate_socket || true
  check_selinux || true

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: would restart service $svc"
    stop_gauge
  else
    if [[ $EUID -eq 0 ]]; then
      systemctl restart "$svc" || true
      log "Restarted $svc as root"
    else
      if sudo -n true 2>/dev/null; then
        sudo systemctl restart "$svc" || true
        log "Restarted $svc via sudo"
      else
        echo "No sudo privileges: please restart the service $svc as root." >&2
      fi
    fi
    stop_gauge
  fi

  log "=== Deploy finished: $(date) ==="
} 2>&1 | tee "$LOG_FILE"

echo "Deploy log: $LOG_FILE"
