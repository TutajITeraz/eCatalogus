#!/usr/bin/env bash
# Update and restart every eCatalogus instance on this server, one after another.
#
# Keep a COPY of this file outside the repositories (e.g. ~/deploy_all_instances.sh):
# every run does `git reset --hard` in each instance, which would rewrite the script
# while bash is still reading it.
#
#   ~/deploy_all_instances.sh                  all instances
#   ~/deploy_all_instances.sh eclla limbo      only these (name from the list below)
#   ~/deploy_all_instances.sh --list           show the instances and exit
#
# A failing instance does not stop the others; the exit code is 1 if any failed.

set -uo pipefail

DOMAINS_ROOT="${DOMAINS_ROOT:-/home/ispan/domains}"

# name | domain directory under $DOMAINS_ROOT | config file in <repo>/scripts/config/
# Order matters only for taste; the master (ecatalogus) is updated before its slaves.
INSTANCES=(
  "mpl|monumenta-poloniae-liturgica.ispan.pl|monumenta-poloniae-liturgica.ispan.pl.env"
  "ecatalogus|ecatalogus.ispan.pl|ecatalogus.ispan.pl.env"
  "limbo|limbo.monumenta-poloniae-liturgica.ispan.pl|limbo.env"
  "canon-missae|canon-missae.ispan.pl|canon-missae.env"
  "corpus-liturgicum|corpus-liturgicum.org|corpus-liturgicum.env"
  "eclla|api.eclla.ecatalogus.ispan.pl|eclla.env"
)

# Extra step after a successful update, per instance name.
post_update() {
  case "$1" in
    eclla)
      # The public UI of eCLLA is a copy of static_assets on eclla.henrybradshawsociety.org.
      tar czf "$HOME/eclla_ui.tgz" -C static_assets . \
        && echo "  UI archive: ~/eclla_ui.tgz  (copy it to the HBS host and unpack into ~/eclla/static, see ECLLA_MIGRATION.md section 4)"
      ;;
  esac
}

update_instance() {
  local name="$1" repo_dir="$2" env_file="$3"

  # Subshell: cd / unset stay local to this instance. `set -e` cannot be used here: the
  # function is called from an `if`, where bash ignores it, so every step is checked by hand.
  (
    cd "$repo_dir" || exit 1
    unset DJANGO_SETTINGS_MODULE INSTANCE_SLUG SERVICE_SHORTNAME

    git rebase --abort 2>/dev/null || true
    git merge --abort  2>/dev/null || true
    git reset --hard HEAD || exit 1

    bash ./scripts/deploy_update.sh "$env_file" || exit 1
    post_update "$name" || exit 1
  )
}

want() {  # is instance $1 selected on the command line?
  [[ ${#SELECTED[@]} -eq 0 ]] && return 0
  local s
  for s in ${SELECTED[@]+"${SELECTED[@]}"}; do [[ "$s" == "$1" ]] && return 0; done
  return 1
}

SELECTED=()
for arg in "$@"; do
  case "$arg" in
    --list)
      for entry in "${INSTANCES[@]}"; do IFS='|' read -r n d e <<<"$entry"; printf '%-18s %s/%s/ecatalogus  (%s)\n' "$n" "$DOMAINS_ROOT" "$d" "$e"; done
      exit 0 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *)  SELECTED+=("$arg") ;;
  esac
done

# Reject unknown names up front instead of silently updating nothing.
for s in ${SELECTED[@]+"${SELECTED[@]}"}; do
  known=0
  for entry in "${INSTANCES[@]}"; do [[ "${entry%%|*}" == "$s" ]] && known=1; done
  [[ $known -eq 1 ]] || { echo "Unknown instance: $s (try --list)" >&2; exit 2; }
done

echo "=== Aktualizacja i deploy instancji ecatalogus ==="
ok=(); failed=(); start_all=$SECONDS

for entry in "${INSTANCES[@]}"; do
  IFS='|' read -r name domain env_file <<<"$entry"
  want "$name" || continue
  repo_dir="$DOMAINS_ROOT/$domain/ecatalogus"

  echo
  echo "→ $name ($domain)"
  if [[ ! -d "$repo_dir/.git" ]]; then
    echo "  BŁĄD: brak repozytorium w $repo_dir" >&2
    failed+=("$name"); continue
  fi

  t0=$SECONDS
  if update_instance "$name" "$repo_dir" "scripts/config/$env_file"; then
    echo "  OK: $name ($((SECONDS - t0))s)"
    ok+=("$name")
  else
    echo "  BŁĄD: $name — patrz komunikaty powyżej" >&2
    failed+=("$name")
  fi
done

echo
echo "=== Podsumowanie ($((SECONDS - start_all))s) ==="
[[ ${#ok[@]}     -gt 0 ]] && echo "OK:     ${ok[*]}"
[[ ${#failed[@]} -gt 0 ]] && echo "BŁĘDY:  ${failed[*]}" >&2
[[ ${#failed[@]} -eq 0 ]]
