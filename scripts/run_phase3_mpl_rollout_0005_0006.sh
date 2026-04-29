#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_ENV_FILE="${SCRIPT_DIR}/config/monumenta-poloniae-liturgica.ispan.pl.env"
ENV_FILE="${1:-$DEFAULT_ENV_FILE}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

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

SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ecatalogus.settings_mpl}"

echo "Phase 3 MPL rollout for migrations 0005 and 0006"
echo "Repo: $APPDIR"
echo "Settings: $SETTINGS_MODULE"
echo "Python: $PYTHON_CMD"
echo
echo "Required before running: current DB backup and media backup already created."
echo "This script does not create backups for you."
echo

cd "$APPDIR"

export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"

"$PYTHON_CMD" manage.py makemigrations indexerapp --noinput
"$PYTHON_CMD" manage.py migrate indexerapp
"$PYTHON_CMD" manage.py populate_uuid_fk --chunk-size 500
"$PYTHON_CMD" manage.py validate_uuid_shadow_fks --chunk-size 500 --fail-on-issues
"$PYTHON_CMD" manage.py export_m2m_uuid_plan --output /tmp/etl_uuid_m2m_plan.tsv
"$PYTHON_CMD" manage.py validate_uuid_m2m --chunk-size 200 --fail-on-issues

echo
echo "Phase 3 MPL rollout commands finished successfully."
echo "Saved M2M plan to /tmp/etl_uuid_m2m_plan.tsv"