#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_ENV_FILE="${SCRIPT_DIR}/config/ecatalogus.ispan.pl.env"
ENV_FILE="${1:-$DEFAULT_ENV_FILE}"
SINCE_VALUE="${2:-}"

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

SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ecatalogus.settings_ecatalogus}"
PEER_ID="${ETL_PULL_PEER_ID:-slave-1}"

cd "$APPDIR"
export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"

extra_args=()
if [[ -n "$SINCE_VALUE" ]]; then
  extra_args+=(--since "$SINCE_VALUE")
fi

echo "eCatalogus ETL dictionary pull"
echo "Repo: $APPDIR"
echo "Settings: $SETTINGS_MODULE"
echo "Peer: $PEER_ID"
if [[ -n "$SINCE_VALUE" ]]; then
  echo "Since: $SINCE_VALUE"
fi
echo

"$PYTHON_CMD" manage.py pull_etl_category --peer "$PEER_ID" --category main "${extra_args[@]}"
"$PYTHON_CMD" manage.py pull_etl_category --peer "$PEER_ID" --category shared "${extra_args[@]}"

echo
echo "eCatalogus ETL dictionary pull finished successfully."