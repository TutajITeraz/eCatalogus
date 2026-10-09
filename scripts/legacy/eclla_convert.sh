#!/usr/bin/env bash
# Rebuild the eCLLA database in the current schema from a dump of the legacy
# (pre-UUID) eclla.ecatalogus.ispan.pl database, and write a dump ready to be
# imported into the new api.eclla.ecatalogus.ispan.pl instance.
#
# Runs locally. Requires a MariaDB account that can create databases (the
# default unix-socket account on a Homebrew install) and .env.eclla.
#
# The master eCatalogus dump is needed so that dictionary rows (formulas, rite
# names, sections, ...) keep the master's UUIDs and a later sync does not
# duplicate them. Take it from production right before the cut-over.
#
# Usage: scripts/legacy/eclla_convert.sh <legacy ispan_eclla.sql> <master ecatalogus.sql> [output.sql]

set -euo pipefail

LEGACY_DUMP="${1:?path to the legacy ispan_eclla SQL dump}"
MASTER_DUMP="${2:?path to a current SQL dump of the master eCatalogus database}"
OUTPUT="${3:-backup/eclla_converted_$(date +%Y%m%d_%H%M).sql}"
LEGACY_DB=eclla_legacy
MASTER_DB=ecatalogus_master_ref
TARGET_DB=eclla
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck source=/dev/null
source .env.eclla
set +a
[[ "$DATABASE_NAME" == "$TARGET_DB" ]] || { echo "DATABASE_NAME in .env.eclla must be ${TARGET_DB}" >&2; exit 1; }

echo "==> Recreating ${LEGACY_DB}, ${MASTER_DB} and ${TARGET_DB}"
mysql -e "DROP DATABASE IF EXISTS ${LEGACY_DB}; DROP DATABASE IF EXISTS ${MASTER_DB}; DROP DATABASE IF EXISTS ${TARGET_DB};
          CREATE DATABASE ${LEGACY_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
          CREATE DATABASE ${MASTER_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
          CREATE DATABASE ${TARGET_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
          GRANT ALL ON ${LEGACY_DB}.* TO '${DATABASE_USER}'@'localhost';
          GRANT ALL ON ${MASTER_DB}.* TO '${DATABASE_USER}'@'localhost';
          GRANT ALL ON ${TARGET_DB}.* TO '${DATABASE_USER}'@'localhost';"

echo "==> Loading legacy and master dumps"
mysql "$LEGACY_DB" < "$LEGACY_DUMP"
mysql "$LEGACY_DB" < scripts/legacy/eclla_prepare.sql
mysql "$MASTER_DB" < "$MASTER_DUMP"

echo "==> Creating the current schema"
.venv/bin/python manage.py migrate --noinput

echo "==> Converting data"
.venv/bin/python scripts/convert_legacy_db.py --legacy-db "$LEGACY_DB" --reference-db "$MASTER_DB" \
    --uuid-override indexerapp_projects:1=44af92f5b4855fc78e1ae2f10615bab8

echo "==> Aligning the eCLLA project row with production"
mysql "$TARGET_DB" -e "UPDATE indexerapp_projects
    SET icon='https://eclla.henrybradshawsociety.org/static/img/logo_flat.svg',
        project_url='https://eclla.henrybradshawsociety.org/'
    WHERE id = 1 AND uuid = '44af92f5b4855fc78e1ae2f10615bab8' AND name = 'eCLLA';
    SELECT ROW_COUNT() AS updated_rows;"

echo "==> Validating"
.venv/bin/python manage.py validate_uuid_integrity | tail -1
.venv/bin/python manage.py validate_uuid_shadow_fks | tail -1
.venv/bin/python manage.py validate_uuid_m2m | tail -1

echo "==> Writing ${OUTPUT}"
mysqldump --single-transaction --default-character-set=utf8mb4 "$TARGET_DB" > "$OUTPUT"
ls -lh "$OUTPUT"
