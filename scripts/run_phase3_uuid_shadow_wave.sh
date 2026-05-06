#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_ENV_FILE="${SCRIPT_DIR}/config/monumenta-poloniae-liturgica.ispan.pl.env"

ENV_FILE=""
CHUNK_SIZE=500
DRY_RUN=0
PLAN_OUTPUT="/tmp/etl_uuid_fk_plan.tsv"
MODEL_ARGS=()
CATEGORY_ARGS=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [config.env] [--model ModelName]... [--category main|shared|ms]... [--chunk-size N] [--plan-output PATH] [--dry-run]
EOF
}

while (($#)); do
  case "$1" in
    --model)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      MODEL_ARGS+=("--model" "$2")
      shift 2
      ;;
    --category)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      CATEGORY_ARGS+=("--category" "$2")
      shift 2
      ;;
    --chunk-size)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      CHUNK_SIZE="$2"
      shift 2
      ;;
    --plan-output)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      PLAN_OUTPUT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [[ -z "$ENV_FILE" ]]; then
        ENV_FILE="$1"
        shift
      else
        echo "Unexpected extra argument: $1" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$ENV_FILE" ]]; then
  ENV_FILE="$DEFAULT_ENV_FILE"
fi

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

echo "Phase 3 UUID shadow wave"
echo "Repo: $APPDIR"
echo "Settings: $SETTINGS_MODULE"
echo "Python: $PYTHON_CMD"
echo "Plan output: $PLAN_OUTPUT"
if ((${#MODEL_ARGS[@]})); then
  echo "Models: ${MODEL_ARGS[*]}"
fi
if ((${#CATEGORY_ARGS[@]})); then
  echo "Categories: ${CATEGORY_ARGS[*]}"
fi
echo
echo "Required before running: current DB backup already created."
echo

cd "$APPDIR"
export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"

"$PYTHON_CMD" manage.py export_uuid_fk_plan --output "$PLAN_OUTPUT"

POPULATE_ARGS=(manage.py populate_uuid_fk --chunk-size "$CHUNK_SIZE")
VALIDATE_ARGS=(manage.py validate_uuid_shadow_fks --chunk-size "$CHUNK_SIZE" --fail-on-issues)

if ((${#MODEL_ARGS[@]})); then
  POPULATE_ARGS+=("${MODEL_ARGS[@]}")
  VALIDATE_ARGS+=("${MODEL_ARGS[@]}")
fi

if ((${#CATEGORY_ARGS[@]})); then
  POPULATE_ARGS+=("${CATEGORY_ARGS[@]}")
  VALIDATE_ARGS+=("${CATEGORY_ARGS[@]}")
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  POPULATE_ARGS+=(--dry-run)
fi

"$PYTHON_CMD" "${POPULATE_ARGS[@]}"

if [[ "$DRY_RUN" -eq 0 ]]; then
  "$PYTHON_CMD" "${VALIDATE_ARGS[@]}"
fi

echo
echo "Phase 3 UUID shadow wave finished successfully."
