#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_ENV_FILE="${SCRIPT_DIR}/config/example.env"
ENV_FILE="${1:-$DEFAULT_ENV_FILE}"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

APPDIR="${APPDIR:-/home/${DEPLOY_USER}/domains/${DOMAIN}/ecatalogus}"
SERVICE_SHORTNAME="${SERVICE_SHORTNAME:?SERVICE_SHORTNAME is required in env file}"
DOMAIN="${DOMAIN:?DOMAIN is required in env file}"
DEPLOY_USER="${DEPLOY_USER:?DEPLOY_USER is required in env file}"

SNIPPET_SRC="${APPDIR}/deploy/nginx_${SERVICE_SHORTNAME}_custom3.conf"
DA_USER_DIR="/usr/local/directadmin/data/users/${DEPLOY_USER}/domains"
TARGET_FILE="${DA_USER_DIR}/${DOMAIN}.conf"
BEGIN_MARKER="# BEGIN COPILOT_CUSTOM3 ${SERVICE_SHORTNAME}"
END_MARKER="# END COPILOT_CUSTOM3 ${SERVICE_SHORTNAME}"

if [[ ! -f "$SNIPPET_SRC" ]]; then
  echo "Snippet not found: $SNIPPET_SRC" >&2
  exit 1
fi

mkdir -p "$DA_USER_DIR"
if [[ -f "$TARGET_FILE" ]]; then
  cp -a "$TARGET_FILE" "${TARGET_FILE}.bak_$(date +%Y%m%d-%H%M%S)"
fi

TMP_FILE=$(mktemp)
if [[ -f "$TARGET_FILE" ]]; then
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
  ' "$TARGET_FILE" > "$TMP_FILE"
fi

{
  cat "$TMP_FILE"
  printf "\n%s\n" "$BEGIN_MARKER"
  cat "$SNIPPET_SRC"
  printf "%s\n" "$END_MARKER"
} > "$TARGET_FILE"
rm -f "$TMP_FILE"

if [[ -x "/usr/local/directadmin/custombuild/build" ]]; then
  /usr/local/directadmin/custombuild/build rewrite_confs
elif [[ -x "/usr/local/directadmin/scripts/rewrite_confs.sh" ]]; then
  /usr/local/directadmin/scripts/rewrite_confs.sh
else
  echo "CUSTOM3 installed into $TARGET_FILE, but DirectAdmin rewrite script was not found. Run rewrite_confs manually." >&2
  exit 1
fi

echo "Installed CUSTOM3 snippet for ${DOMAIN} from ${SNIPPET_SRC}"