#!/usr/bin/env bash
set -euo pipefail

# Reports which records changed recently on an instance, by entry_date.
# Usage: run_etl_recent_changes.sh [env-file] [extra etl_recent_changes args...]
#   scripts/run_etl_recent_changes.sh scripts/config/limbo.env --hours 6
#   scripts/run_etl_recent_changes.sh scripts/config/limbo.env --hours 48 --summary

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_ENV_FILE="${SCRIPT_DIR}/config/ecatalogus.ispan.pl.env"

if [[ $# -gt 0 && -f "$1" ]]; then
  ENV_FILE="$1"
  shift
else
  ENV_FILE="$DEFAULT_ENV_FILE"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

# scripts/config/*.env carry the server-side APPDIR; a local .env.<instance> has none,
# so this checkout is used instead and the same wrapper works on both sides.
if [[ -z "${APPDIR:-}" ]]; then
  APPDIR="$REPO_DIR"
fi

if [[ -z "${VENV_PATH:-}" ]]; then
  VENV_PATH="${APPDIR}/.venv"
fi

if [[ -x "${VENV_PATH}/bin/python" ]]; then
  PYTHON_CMD="${VENV_PATH}/bin/python"
else
  PYTHON_CMD="python"
fi

SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ecatalogus.settings_ecatalogus}"

cd "$APPDIR"
export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"

echo "eCatalogus ETL recent changes"
echo "Repo: $APPDIR"
echo "Settings: $SETTINGS_MODULE"
echo

if [[ $# -eq 0 ]]; then
  set -- --hours 24
fi

"$PYTHON_CMD" manage.py etl_recent_changes "$@"
