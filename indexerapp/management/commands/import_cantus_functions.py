"""Import the Cantus Index genre -> ContentFunctions mapping prepared for Ritus+.

Input is a TSV with the columns ``function_name, action, parent_function,
cantus_codes, n_codes``. ``CREATE`` rows add a function (parents first, whether
they already exist or come from the same file); ``UPDATE (exists)`` rows only
fill ``cantus_codes`` of a function found by name, case-insensitively.

The whole file is validated before anything is written, and any problem —
a name collision, an unmatched UPDATE, a code claimed twice — aborts the run
with nothing saved. Re-running a finished import is a no-op, so the command is
safe to repeat. New rows get their UUID from the usual pre_save signal, like
every other dictionary entry curated in eCatalogus.
"""

import csv
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from etlapp.main_guard import MainReadOnlyError, assert_main_writable
from indexerapp.models import ContentFunctions


ACTION_CREATE = 'CREATE'
ACTION_UPDATE = 'UPDATE (exists)'
EXPECTED_COLUMNS = ('function_name', 'action', 'parent_function', 'cantus_codes', 'n_codes')

#: Cantus placeholders for unknown or mixed genres — never a function of their own.
TECHNICAL_CANTUS_CODES = frozenset({'[?]', '[G]', '[GV]', '[M]', '[MO]'})


@dataclass
class SourceRow:
    line: int
    name: str
    action: str
    parent: str
    codes: list


@dataclass
class ImportPlan:
    creates: list = field(default_factory=list)  # SourceRow, parents before children
    updates: list = field(default_factory=list)  # (SourceRow, existing name, old codes)
    unchanged: list = field(default_factory=list)  # (SourceRow, reason)
    name_collisions: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def read_source_rows(handle):
    """Parse the TSV; returns (rows, problems)."""
    reader = csv.DictReader(handle, delimiter='\t')
    missing = [column for column in EXPECTED_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        return [], [f'Header is missing column(s): {", ".join(missing)}.']

    rows, problems = [], []
    for line, record in enumerate(reader, start=2):
        name = (record['function_name'] or '').strip()
        action = (record['action'] or '').strip()
        parent = (record['parent_function'] or '').strip()
        raw_codes = record['cantus_codes'] or ''
        codes = [code.strip() for code in raw_codes.split(',') if code.strip()]

        if not name:
            problems.append(f'line {line}: empty function_name.')
            continue
        if action not in (ACTION_CREATE, ACTION_UPDATE):
            problems.append(f'line {line} "{name}": unknown action "{action}".')
            continue
        if not codes:
            problems.append(f'line {line} "{name}": no Cantus codes.')
        if any(any(char.isspace() for char in code) for code in codes):
            problems.append(f'line {line} "{name}": Cantus code with whitespace in "{raw_codes}".')
        if len(set(codes)) != len(codes):
            problems.append(f'line {line} "{name}": repeated Cantus code in "{raw_codes}".')
        technical = sorted(TECHNICAL_CANTUS_CODES.intersection(codes))
        if technical:
            problems.append(
                f'line {line} "{name}": technical Cantus code(s) {", ".join(technical)} '
                'must not be mapped to a function.'
            )
        n_codes = (record['n_codes'] or '').strip()
        if n_codes and n_codes != str(len(codes)):
            problems.append(f'line {line} "{name}": n_codes is {n_codes} but {len(codes)} code(s) listed.')

        rows.append(SourceRow(line=line, name=name, action=action, parent=parent, codes=codes))

    return rows, problems


def build_plan(rows, existing):
    """Decide what to do with every row without touching the database.

    ``existing`` is a list of dicts with ``name``, ``cantus_codes`` and
    ``parent_name`` for every ContentFunctions row currently stored.
    """
    plan = ImportPlan()
    existing_by_key = {record['name'].casefold(): record for record in existing}

    code_owners = {}
    for record in existing:
        for code in ContentFunctions.split_cantus_codes(record['cantus_codes']):
            code_owners.setdefault(code, record['name'])

    seen_names = {}
    seen_codes = {}
    for row in rows:
        key = row.name.casefold()
        if key in seen_names:
            plan.problems.append(
                f'line {row.line} "{row.name}": function listed twice (also line {seen_names[key]}).'
            )
        seen_names.setdefault(key, row.line)
        for code in row.codes:
            if code in seen_codes and seen_codes[code][1].casefold() != key:
                other_line, other_name = seen_codes[code]
                plan.problems.append(
                    f'line {row.line} "{row.name}": Cantus code "{code}" is also given to '
                    f'"{other_name}" (line {other_line}).'
                )
            seen_codes.setdefault(code, (row.line, row.name))

    create_rows = {}
    for row in rows:
        match = existing_by_key.get(row.name.casefold())
        target_name = match['name'] if match else row.name

        for code in row.codes:
            owner = code_owners.get(code)
            if owner is not None and owner.casefold() != target_name.casefold():
                plan.problems.append(
                    f'line {row.line} "{row.name}": Cantus code "{code}" already belongs to "{owner}".'
                )

        if row.action == ACTION_CREATE:
            if match is None:
                create_rows[row.name.casefold()] = row
                continue
            same_parent = (match['parent_name'] or '').casefold() == row.parent.casefold()
            current_codes = ContentFunctions.split_cantus_codes(match['cantus_codes'])
            if match['name'] == row.name and current_codes == row.codes and same_parent:
                plan.unchanged.append((row, 'already created by an earlier run'))
                continue
            collision = f'line {row.line}: CREATE "{row.name}" collides with existing "{match["name"]}"'
            plan.name_collisions.append(collision)
            plan.problems.append(f'{collision} — no duplicate created; resolve by hand.')
            continue

        # UPDATE (exists)
        if match is None:
            plan.problems.append(
                f'line {row.line}: UPDATE "{row.name}" matches no existing function (case-insensitive).'
            )
            continue
        if match['name'] != row.name:
            plan.warnings.append(
                f'line {row.line}: UPDATE "{row.name}" matched "{match["name"]}" (different case); '
                'its name is kept.'
            )
        if row.parent and row.parent.casefold() != (match['parent_name'] or '').casefold():
            plan.warnings.append(
                f'line {row.line}: parent "{row.parent}" ignored for UPDATE "{match["name"]}" '
                f'(current parent: "{match["parent_name"] or ""}").'
            )
        current_codes = ContentFunctions.split_cantus_codes(match['cantus_codes'])
        if current_codes == row.codes:
            plan.unchanged.append((row, 'codes already set'))
        elif current_codes:
            plan.problems.append(
                f'line {row.line}: "{match["name"]}" already has Cantus codes '
                f'"{match["cantus_codes"]}"; the file says "{",".join(row.codes)}". Not overwritten.'
            )
        else:
            plan.updates.append((row, match['name'], match['cantus_codes']))

    # Parents first: a CREATE row waits until its parent exists or is scheduled.
    pending = dict(create_rows)
    scheduled = set()
    while pending:
        ready = [
            key for key, row in pending.items()
            if not row.parent
            or row.parent.casefold() in existing_by_key
            or row.parent.casefold() in scheduled
        ]
        if not ready:
            break
        for key in ready:
            plan.creates.append(pending.pop(key))
            scheduled.add(key)

    for row in pending.values():
        if row.parent.casefold() in create_rows:
            plan.problems.append(f'line {row.line} "{row.name}": parent "{row.parent}" is part of a cycle.')
        else:
            plan.problems.append(
                f'line {row.line} "{row.name}": parent "{row.parent}" is neither an existing '
                'function nor created by this file.'
            )

    # The content API resolves function_id by name before code; a code that is
    # also some other function's name would never be reached.
    all_names = {record['name'].casefold(): record['name'] for record in existing}
    all_names.update({key: row.name for key, row in create_rows.items()})
    for row in rows:
        target = existing_by_key.get(row.name.casefold(), {}).get('name', row.name)
        for code in row.codes:
            other = all_names.get(code.casefold())
            if other is not None and other.casefold() != target.casefold():
                plan.warnings.append(
                    f'line {row.line}: Cantus code "{code}" equals the name of "{other}"; '
                    'the content API will resolve it to that function by name.'
                )

    return plan


def load_existing_functions():
    parents = dict(ContentFunctions.objects.values_list('uuid', 'name'))
    return [
        {
            'name': name,
            'cantus_codes': codes,
            'parent_name': parents.get(parent_uuid) if parent_uuid else None,
        }
        for name, codes, parent_uuid in ContentFunctions.objects.values_list(
            'name', 'cantus_codes', 'parent_function_uuid'
        )
    ]


class Command(BaseCommand):
    help = (
        'Creates ContentFunctions for Cantus Index genres and fills cantus_codes from a TSV '
        '(function_name, action, parent_function, cantus_codes, n_codes). Idempotent; '
        'all-or-nothing.'
    )

    def add_arguments(self, parser):
        parser.add_argument('tsv_file', type=str, help='Path to the TSV file')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be created and updated, and every conflict, without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbosity = options['verbosity']

        if not dry_run:
            try:
                assert_main_writable('ContentFunctions', subject='Content functions')
            except MainReadOnlyError as exc:
                raise CommandError(str(exc))

        try:
            with open(options['tsv_file'], newline='', encoding='utf-8') as handle:
                rows, problems = read_source_rows(handle)
        except OSError as exc:
            raise CommandError(f'Cannot read {options["tsv_file"]}: {exc}')

        existing = load_existing_functions()
        plan = build_plan(rows, existing)
        plan.problems[:0] = problems

        self._report(options['tsv_file'], rows, existing, plan, dry_run, verbosity)

        if plan.problems:
            raise CommandError(f'{len(plan.problems)} problem(s) found; nothing was written.')
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run: nothing was written.'))
            return
        if not plan.creates and not plan.updates:
            self.stdout.write(self.style.SUCCESS('Nothing to do: the file is already imported.'))
            return

        try:
            with transaction.atomic():
                self._apply(plan)
        except ValidationError as exc:
            raise CommandError(f'Validation failed, nothing was written: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(plan.creates)} and updated {len(plan.updates)} content function(s).'
        ))

    def _apply(self, plan):
        functions = {function.name.casefold(): function for function in ContentFunctions.objects.all()}

        for row in plan.creates:
            parent = functions[row.parent.casefold()] if row.parent else None
            function = ContentFunctions(
                name=row.name,
                parent_function_uuid=parent,
                cantus_codes=','.join(row.codes),
            )
            function.full_clean()
            function.save()
            functions[row.name.casefold()] = function

        for row, existing_name, _old_codes in plan.updates:
            function = functions[existing_name.casefold()]
            function.cantus_codes = ','.join(row.codes)
            function.full_clean()
            function.save()

    def _report(self, path, rows, existing, plan, dry_run, verbosity):
        verb = 'Would' if dry_run else 'Will'
        write = self.stdout.write

        write(f'Source: {path} ({len(rows)} row(s))')
        write(f'Existing content functions: {len(existing)}')
        write(f'{verb} create: {len(plan.creates)}')
        write(f'{verb} update cantus_codes: {len(plan.updates)}')
        write(f'Unchanged (already imported): {len(plan.unchanged)}')

        if verbosity >= 2:
            for row in plan.creates:
                parent = f' (parent: {row.parent})' if row.parent else ''
                write(f'  + {row.name}{parent} [{",".join(row.codes)}]')
            for row, existing_name, _old_codes in plan.updates:
                write(f'  ~ {existing_name} [{",".join(row.codes)}]')
            for row, reason in plan.unchanged:
                write(f'  = {row.name}: {reason}')

        write(f'Name collisions: {len(plan.name_collisions) or "none"}')
        for collision in plan.name_collisions:
            write(self.style.ERROR(f'  {collision}'))

        if plan.warnings:
            write(f'Warnings: {len(plan.warnings)}')
            for warning in plan.warnings:
                write(self.style.WARNING(f'  {warning}'))

        write(f'Problems: {len(plan.problems) or "none"}')
        for problem in plan.problems:
            write(self.style.ERROR(f'  {problem}'))
