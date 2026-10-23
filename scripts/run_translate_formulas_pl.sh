#!/usr/bin/env bash
set -euo pipefail

# Translates Formulas.text (Latin) into translation_pl with Ollama translategemma,
# running in the background so it survives logout.
# Usage: run_translate_formulas_pl.sh <start|status|log|stop> [env-file] [extra translate_formulas_pl args...]
#   scripts/run_translate_formulas_pl.sh start
#   scripts/run_translate_formulas_pl.sh start scripts/config/ecatalogus.ispan.pl.env --limit 20 --dry-run
#   scripts/run_translate_formulas_pl.sh status
#   scripts/run_translate_formulas_pl.sh log      # follow the output (Ctrl+C only stops following)
#   scripts/run_translate_formulas_pl.sh stop     # finishes the current formula, then exits; start resumes
# Model comparison (saves nothing; one model loaded at a time, unloaded afterwards):
#   scripts/run_translate_formulas_pl.sh start scripts/config/ecatalogus.ispan.pl.env \
#     --compare translategemma:4b,translategemma:12b,translategemma:27b --sample 15
#   -> follow with `log`; side-by-side CSV in logs/translate_formulas_pl.compare.csv

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
DEFAULT_ENV_FILE="${SCRIPT_DIR}/config/ecatalogus.ispan.pl.env"

ACTION="${1:-status}"
[[ $# -gt 0 ]] && shift

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
if [[ -z "${APPDIR:-}" || ! -d "${APPDIR}" ]]; then
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

LOG_DIR="${APPDIR}/logs"
LOG_FILE="${LOG_DIR}/translate_formulas_pl.log"
PID_FILE="${LOG_DIR}/translate_formulas_pl.pid"
PROGRESS_FILE="${LOG_DIR}/translate_formulas_pl.progress.json"
mkdir -p "$LOG_DIR"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

case "$ACTION" in
  start)
    if is_running; then
      echo "Already running (pid $(cat "$PID_FILE")). Use status/log/stop." >&2
      exit 1
    fi
    cd "$APPDIR"
    export DJANGO_SETTINGS_MODULE="$SETTINGS_MODULE"
    export PYTHONUNBUFFERED=1
    {
      echo
      echo "=== $(date '+%Y-%m-%d %H:%M:%S') start: $* ==="
    } >> "$LOG_FILE"
    nohup "$PYTHON_CMD" manage.py translate_formulas_pl --progress-file "$PROGRESS_FILE" "$@" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started (pid $!). Settings: $SETTINGS_MODULE"
    echo "Log: $LOG_FILE"
    echo "Progress: $0 status"
    ;;
  status)
    if is_running; then
      echo "Process: running (pid $(cat "$PID_FILE"))"
    else
      echo "Process: not running"
    fi
    if [[ -f "$PROGRESS_FILE" ]]; then
      "$PYTHON_CMD" - "$PROGRESS_FILE" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
total, done, failed = p['total'], p['done'], p['failed']
processed = done + failed
pct = 100 * processed / total if total else 100
eta = p.get('eta_seconds') or 0
print(f"Status:   {p['status']}{' (dry run)' if p.get('dry_run') else ''}, model {p['model']}, started {p['started_at']}")
print(f"Progress: {processed}/{total} ({pct:.1f}%), {done} translated, {failed} failed")
if p.get('avg_seconds'):
    print(f"Speed:    {p['avg_seconds']}s per formula, ETA {eta // 3600}h {eta % 3600 // 60}m")
if p.get('failed_ids'):
    print(f"Failed:   {', '.join(map(str, p['failed_ids'][-20:]))}")
if p.get('last_id'):
    print(f"Last #{p['last_id']}:")
    print(f"  la: {p['last_text'][:200]}")
    print(f"  pl: {p['last_translation'][:200]}")
PY
    else
      echo "No progress file yet: $PROGRESS_FILE"
    fi
    ;;
  log)
    tail -n 40 -f "$LOG_FILE"
    ;;
  stop)
    if is_running; then
      kill -TERM "$(cat "$PID_FILE")"
      echo "Stop requested (pid $(cat "$PID_FILE")); it exits after the current formula."
    else
      echo "Not running."
    fi
    ;;
  *)
    echo "Usage: $0 <start|status|log|stop> [env-file] [translate_formulas_pl args...]" >&2
    exit 1
    ;;
esac
