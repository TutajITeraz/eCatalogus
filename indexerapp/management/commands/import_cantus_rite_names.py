"""Import the Cantus Index feasts into RiteNames from the Ritus+ plan TSV.

Columns: action, cantus_feast_code, target_name_cantus, ecatalogus_uuid,
ecatalogus_legacy_id, ecatalogus_current_name, name_changes, similarity,
description_en, feast_date, alt_names, note.

* ``UPDATE_RENAME``: (a row without a Cantus code only renames) the rite found by ``ecatalogus_uuid`` gets the Cantus name
  and code — only if its current name still matches ``ecatalogus_current_name``
  (case and whitespace aside) and the new name is not taken by another rite;
* ``REVIEW_UPDATE``: same, except rows whose ``note`` says "similar to an
  existing rite name" (approximate matches): they change nothing and go to
  ``rite_names_skipped_review.tsv`` for a human, unless listed in ``--confirmed``;
* ``CREATE``: a new rite, unless the name already exists (case-insensitively);
* ``SKIP_TECHNICAL``: ignored.

Temporary codes (``tempNNNN``) are only labels in the plan and are never stored.
A ``temp`` row is recognised on a re-run by its exact name. Rows that are the
same feast twice inside Cantus ("duplicate inside Cantus" with an identical
name) make ONE rite that keeps the code without ``temp``; the other code is
reported as pointing to the same uuid.

A row whose code is already stored updates that rite instead, so a second run
changes nothing. An ``english_translation`` is filled when empty and replaced
when the stored one ends in "…" (cut by an earlier import); hand-edited values
are left alone. Rows that fail a check are skipped and reported; the rest is
written in one transaction, and only with ``--apply`` (``--dry-run`` forces a
dry run). With ``--apply`` the command also writes ``rite_names_import_result.tsv``
(every code of the plan -> uuid) and ``rite_names_skipped_review.tsv`` to
``--output-dir``. New rites get their id
from the table's auto-increment and their UUID from the pre_save signal, like
any rite added in the admin. ``feast_date`` and ``alt_names`` have no field in
RiteNames and are ignored.
"""

import csv
import html
import re
from pathlib import Path
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from etlapp.main_guard import MainReadOnlyError, assert_main_writable
from etlapp.uuid_utils import build_deterministic_sync_uuid
from indexerapp.models import RiteNames


ACTION_UPDATE = 'UPDATE_RENAME'
ACTION_REVIEW = 'REVIEW_UPDATE'
ACTION_CREATE = 'CREATE'
ACTION_SKIP = 'SKIP_TECHNICAL'
ACTIONS = (ACTION_UPDATE, ACTION_REVIEW, ACTION_CREATE, ACTION_SKIP)
EXPECTED_COLUMNS = (
    'action', 'cantus_feast_code', 'target_name_cantus', 'ecatalogus_uuid',
    'ecatalogus_legacy_id', 'ecatalogus_current_name', 'description_en',
)

#: Cantus feasts verified as different from a similar-looking eCatalogus rite:
#: (Cantus code, Cantus name, legacy id of the existing rite, its correct name).
#: An earlier version of the plan could have merged them; the command undoes that.
VERIFIED_DIFFERENT = (
    ('13013000', 'Pro defunctis regibus', 3713, 'pro defunctis parentibus'),
    ('16030010', 'Pro peregrinantibus', 3862, 'pro praegnantibus'),
    ('14120700', 'Victoris', 3288, 'Victorinus'),
    ('14012920', 'Constantii', 958, 'Constantia'),
    ('14032100', 'Benedicti', 688, 'Benedicta'),
)
#: Benedicta legitimately carries the code of "Benedictae" (the owner confirmed it; the plan renames it).
VERIFIED_DIFFERENT_ALLOWED_CODES = {688: '14100810'}

SIMILAR_NOTE = 'similar to an existing rite name'
DUPLICATE_NOTE = 'duplicate inside cantus'
TEMP_CODE = re.compile(r'^temp\d+$')

TRANSLATION_MAX_LENGTH = RiteNames._meta.get_field('english_translation').max_length


def clean_description(value):
    """Plain text from a Cantus description: no tags, entities decoded, whitespace collapsed."""
    text = re.sub(r'<[^>]+>', ' ', value or '')
    text = html.unescape(text).replace('\xa0', ' ')
    return ' '.join(text.split())


def fit_translation(text):
    """Return (text, truncated) with text no longer than the column allows."""
    if len(text) <= TRANSLATION_MAX_LENGTH:
        return text, False
    cut = text[:TRANSLATION_MAX_LENGTH - 1]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' ,;:') + '…', True


def is_temp(code):
    return bool(TEMP_CODE.match(code or ''))


def find_duplicate_aliases(rows):
    """{alias code: canonical code} for CREATE rows that are one feast listed twice in Cantus.

    The canonical code is the one without ``temp`` (else the first in the file).
    """
    groups = {}
    for _line, row in rows:
        if row['action'] == ACTION_CREATE and DUPLICATE_NOTE in (row.get('note') or '').casefold():
            name = ' '.join((row['target_name_cantus'] or '').split()).casefold()
            groups.setdefault(name, []).append((row['cantus_feast_code'] or '').strip())
    aliases = {}
    for codes in groups.values():
        codes = [c for c in dict.fromkeys(codes) if c]
        if len(codes) < 2:
            continue
        canonical = next((c for c in codes if not is_temp(c)), codes[0])
        aliases.update({c: canonical for c in codes if c != canonical})
    return aliases


def same_name(left, right):
    return ' '.join((left or '').split()).casefold() == ' '.join((right or '').split()).casefold()


@dataclass
class Report:
    created: list = field(default_factory=list)
    renamed: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    review_skipped: list = field(default_factory=list)
    technical_skipped: list = field(default_factory=list)
    missing_uuid: list = field(default_factory=list)
    name_mismatch: list = field(default_factory=list)
    name_collision: list = field(default_factory=list)
    code_conflict: list = field(default_factory=list)
    invalid: list = field(default_factory=list)
    truncated: list = field(default_factory=list)
    pairs: list = field(default_factory=list)
    confirmed_unused: list = field(default_factory=list)
    aliases: list = field(default_factory=list)

    db_rejected: list = field(default_factory=list)

    @property
    def skipped_with_error(self):
        return (self.missing_uuid + self.name_mismatch + self.name_collision
                + self.code_conflict + self.invalid + self.db_rejected)


class _DryRunRollback(Exception):
    pass


class Planner:
    """Works out every change against an in-memory copy of RiteNames.

    Each planned change is applied to the copy straight away, so later rows see
    the effect of earlier ones (a name created two rows up is already taken).
    ``operations`` is what --apply executes, in order.
    """

    def __init__(self, existing, confirmed_codes, aliases=None):
        self.records = {record['pk']: record for record in existing}
        self.by_uuid = {str(record['uuid']): record['pk'] for record in existing if record['uuid']}
        self.name_owner = {record['name'].casefold(): record['pk'] for record in existing}
        self.code_owner = {
            record['cantus_feast_code']: record['pk']
            for record in existing if record['cantus_feast_code']
        }
        self.confirmed = set(confirmed_codes)
        self.aliases = dict(aliases or {})
        #: one entry per plan row: (code, key or None, status, target name, row)
        self.outcomes = []
        #: REVIEW_UPDATE rows left for a human: (code, cantus name, uuid, current name)
        self.review_rows = []
        self.operations = []
        self.report = Report()
        self._new_keys = 0

    # -- bookkeeping ----------------------------------------------------

    def _set(self, key, changes, bucket, entry):
        record = self.records[key]
        if 'name' in changes:
            if self.name_owner.get(record['name'].casefold()) == key:
                del self.name_owner[record['name'].casefold()]
            self.name_owner[changes['name'].casefold()] = key
        if 'cantus_feast_code' in changes:
            if record['cantus_feast_code']:
                self.code_owner.pop(record['cantus_feast_code'], None)
            if changes['cantus_feast_code']:
                self.code_owner[changes['cantus_feast_code']] = key
        record.update(changes)
        self.operations.append(('update', key, dict(changes), bucket, entry))

    def _create(self, values, entry):
        self._new_keys += 1
        key = f'new:{self._new_keys}'
        self.records[key] = {'pk': key, 'uuid': None, **values}
        self.name_owner[values['name'].casefold()] = key
        if values['cantus_feast_code']:
            self.code_owner[values['cantus_feast_code']] = key
        self.operations.append(('create', key, dict(values), 'created', entry))

    def _label(self, key):
        record = self.records[key]
        return f'"{record["name"]}" (id {record["pk"]})' if not str(key).startswith('new:') else f'"{record["name"]}" (new)'

    def _translation(self, row, line):
        text = clean_description(row['description_en'])
        text, truncated = fit_translation(text)
        if truncated:
            self.report.truncated.append(
                f'line {line} {row["cantus_feast_code"]} "{row["target_name_cantus"]}": '
                f'cut to {TRANSLATION_MAX_LENGTH} characters'
            )
        return text

    # -- the five verified pairs ------------------------------------------

    def check_verified_pairs(self):
        for code, cantus_name, legacy_id, keep_name in VERIFIED_DIFFERENT:
            label = f'{keep_name} (legacy {legacy_id}) vs Cantus "{cantus_name}" {code}'
            key = self.by_uuid.get(str(build_deterministic_sync_uuid('indexerapp.RiteNames', legacy_id)))
            if key is None:
                self.report.pairs.append(f'{label}: rite not found — nothing to check')
                continue

            record = self.records[key]
            changes, notes = {}, []
            if same_name(record['name'], cantus_name):
                holder = self.name_owner.get(keep_name.casefold())
                if holder not in (None, key):
                    notes.append(f'has the Cantus name but "{keep_name}" is taken by {self._label(holder)} — fix by hand')
                else:
                    changes['name'] = keep_name
                    notes.append(f'name restored from "{record["name"]}"')
            elif not same_name(record['name'], keep_name):
                notes.append(f'unexpected current name "{record["name"]}" — left alone')

            current_code = record['cantus_feast_code']
            allowed = VERIFIED_DIFFERENT_ALLOWED_CODES.get(legacy_id)
            if current_code and current_code != allowed:
                changes['cantus_feast_code'] = None
                notes.append(f'Cantus code {current_code} removed')

            entry = f'{label}: ' + ('; '.join(notes) if notes else 'OK, untouched')
            if changes:
                self._set(key, changes, 'pairs', entry)
            self.report.pairs.append(entry)

    # -- rows -----------------------------------------------------------------

    def _outcome(self, code, key, status, name):
        if not code:  # a rename-only row has no Cantus code, so nothing to map
            return
        self.outcomes.append((code, key, status, name))

    def plan_row(self, row, line):
        action = row['action']
        code = (row['cantus_feast_code'] or '').strip()
        name = row['target_name_cantus'] or ''
        tag = f'line {line} {code} "{name}"'

        if action == ACTION_SKIP:
            self.report.technical_skipped.append(tag)
            return
        if action not in ACTIONS:
            self.report.invalid.append(f'{tag}: unknown action "{action}"')
            return
        if not name.strip() or (not code and action != ACTION_UPDATE):
            self.report.invalid.append(f'{tag}: empty code or name')
            return
        if len(code) > 32 or len(name) > RiteNames._meta.get_field('name').max_length:
            self.report.invalid.append(f'{tag}: code or name too long')
            self._outcome(code, None, 'error_invalid', name)
            return
        if action == ACTION_CREATE and code in self.aliases:
            self.report.aliases.append(f'{tag}: same feast as {self.aliases[code]}, one rite for both')
            self._outcome(code, ('alias', self.aliases[code]), 'duplicate_of_' + self.aliases[code], name)
            return
        if action == ACTION_REVIEW and SIMILAR_NOTE in (row.get('note') or '').casefold() \
                and code not in self.confirmed:
            self.report.review_skipped.append(
                f'{tag} -> would update "{row["ecatalogus_current_name"]}" (legacy {row["ecatalogus_legacy_id"]})'
            )
            self.review_rows.append((code, name, row['ecatalogus_uuid'], row['ecatalogus_current_name']))
            self._outcome(code, None, 'skipped_review', name)
            return

        target_code = None if is_temp(code) else code
        if action == ACTION_CREATE:
            key = self.code_owner.get(code)
            if key is None and target_code is None:
                # A temp row on a re-run: the rite made last time has this very name and no code.
                holder = self.name_owner.get(name.casefold())
                if holder is not None and self.records[holder]['name'] == name \
                        and not self.records[holder]['cantus_feast_code']:
                    key = holder
            if key is None:
                self._plan_create(row, line, code, target_code, name, tag)
                return
        else:
            key = self.by_uuid.get((row['ecatalogus_uuid'] or '').strip())
            if key is None:
                self.report.missing_uuid.append(f'{tag}: no rite with uuid {row["ecatalogus_uuid"]}')
                self._outcome(code, None, 'error_missing_uuid', name)
                return
            owner = self.code_owner.get(code)
            if owner not in (None, key):
                self.report.code_conflict.append(f'{tag}: code already belongs to {self._label(owner)}')
                self._outcome(code, None, 'error_code_conflict', name)
                return
            record = self.records[key]
            if not (same_name(record['name'], row['ecatalogus_current_name']) or record['name'] == name):
                self.report.name_mismatch.append(
                    f'{tag}: uuid {row["ecatalogus_uuid"]} is "{record["name"]}", '
                    f'plan expects "{row["ecatalogus_current_name"]}" (legacy {row["ecatalogus_legacy_id"]})'
                )
                self._outcome(code, None, 'error_name_mismatch', name)
                return

        self._plan_update(row, line, key, code, target_code, name, tag)

    def _plan_create(self, row, line, code, target_code, name, tag):
        holder = self.name_owner.get(name.casefold())
        if holder is not None:
            self.report.name_collision.append(f'{tag}: name already used by {self._label(holder)}')
            self._outcome(code, None, 'error_name_collision', name)
            return
        self._create({
            'name': name,
            'english_translation': self._translation(row, line),
            'cantus_feast_code': target_code,
        }, tag)
        self.report.created.append(tag)
        self._outcome(code, f'new:{self._new_keys}', 'created', name)

    def _plan_update(self, row, line, key, code, target_code, name, tag):
        record = self.records[key]
        holder = self.name_owner.get(name.casefold())
        if holder not in (None, key):
            self.report.name_collision.append(f'{tag}: name already used by {self._label(holder)}')
            self._outcome(code, None, 'error_name_collision', name)
            return

        if not code:  # rename only: the rite keeps whatever Cantus code it has
            target_code = record['cantus_feast_code']
        changes = {}
        if record['name'] != name:
            changes['name'] = name
        if record['cantus_feast_code'] != target_code:
            changes['cantus_feast_code'] = target_code
        current = (record['english_translation'] or '').strip()
        translation = self._translation(row, line)
        if translation and translation != current and (not current or current.endswith('\u2026')):
            changes['english_translation'] = translation

        if not changes:
            self.report.unchanged.append(tag)
            self._outcome(code, key, 'unchanged', name)
            return
        if 'name' in changes:
            bucket, entry, status = 'renamed', f'{tag}: renamed from "{record["name"]}"', 'renamed'
        else:
            bucket, entry, status = 'updated', tag, 'updated'
        self._set(key, changes, bucket, entry)
        getattr(self.report, bucket).append(entry)
        self._outcome(code, key, status, name)

    def finish(self, rows):
        review_codes = {
            (row['cantus_feast_code'] or '').strip() for row in rows if row['action'] == ACTION_REVIEW
        }
        self.report.confirmed_unused = sorted(self.confirmed - review_codes)


def read_rows(path):
    with open(path, newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        missing = [column for column in EXPECTED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise CommandError(f'Header is missing column(s): {", ".join(missing)}.')
        rows = []
        for row in reader:
            # reader.line_num is the last physical line of a multi-line record.
            rows.append((reader.line_num, row))
        return rows


def read_confirmed(path):
    if not path:
        return set()
    codes = set()
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.split('#', 1)[0].strip()
            codes.update(token for token in re.split(r'[\s,]+', line) if token)
    return codes


def load_existing():
    return [
        {'pk': pk, 'uuid': uuid, 'name': name, 'english_translation': translation, 'cantus_feast_code': code}
        for pk, uuid, name, translation, code in RiteNames.objects.values_list(
            'pk', 'uuid', 'name', 'english_translation', 'cantus_feast_code'
        )
    ]


class Command(BaseCommand):
    help = (
        'Imports Cantus Index feasts into RiteNames from 02c_rite_names_import_plan.tsv. '
        'Dry run unless --apply is given.'
    )

    def add_arguments(self, parser):
        parser.add_argument('tsv_file', type=str, help='Path to the plan TSV')
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run).')
        parser.add_argument('--dry-run', action='store_true', help='Report only, even together with --apply.')
        parser.add_argument(
            '--output-dir', default='.',
            help='Where --apply writes rite_names_import_result.tsv and rite_names_skipped_review.tsv.',
        )
        parser.add_argument(
            '--confirmed',
            help='File with REVIEW_UPDATE Cantus codes approved for update (whitespace/comma separated, # comments).',
        )

    def handle(self, *args, **options):
        apply = options['apply'] and not options['dry_run']
        if apply:
            try:
                assert_main_writable('RiteNames', subject='Rite names')
            except MainReadOnlyError as exc:
                raise CommandError(str(exc))

        try:
            rows = read_rows(options['tsv_file'])
            confirmed = read_confirmed(options['confirmed'])
        except OSError as exc:
            raise CommandError(str(exc))

        planner = Planner(load_existing(), confirmed, find_duplicate_aliases(rows))
        planner.check_verified_pairs()
        for line, row in rows:
            planner.plan_row(row, line)
        planner.finish([row for _line, row in rows])

        # The dry run performs the very same writes and rolls them back, so the
        # database's own unique checks (utf8mb4_unicode_ci also ignores accents)
        # are part of the report, not a surprise during --apply.
        try:
            with transaction.atomic():
                self._execute(planner.operations, planner.report)
                results = self._results(planner)
                if not apply:
                    raise _DryRunRollback
        except _DryRunRollback:
            pass

        self._report(options['tsv_file'], len(rows), planner.report, apply, options['verbosity'])
        if apply:
            self._write_files(Path(options['output_dir']), results, planner.review_rows)
            self.stdout.write(self.style.SUCCESS('Changes written.'))
        else:
            self.stdout.write(self.style.SUCCESS('Dry run: nothing was written. Re-run with --apply to write.'))

    def _results(self, planner):
        """[(code, uuid, legacy_id, name, status)] for every code of the plan, read inside the transaction."""
        def real_pk(key):
            return self.created_pk.get(key) if isinstance(key, str) else key

        pks = {real_pk(key) for _c, key, _s, _n in planner.outcomes if key is not None and not isinstance(key, tuple)} - {None}
        info = {
            pk: (uuid, name, code) for pk, uuid, name, code in
            RiteNames.objects.filter(pk__in=pks).values_list('pk', 'uuid', 'name', 'cantus_feast_code')
        }
        by_code = {}
        rows = []
        for code, key, status, name in planner.outcomes:
            if key is None or isinstance(key, tuple):
                rows.append([code, '', '', name, status, key])
                continue
            pk = real_pk(key)
            if pk is None or pk not in info:
                rows.append([code, '', '', name, 'error_db_rejected', None])
                continue
            uuid, stored_name, _stored_code = info[pk]
            rows.append([code, str(uuid), str(pk), stored_name, status, None])
            by_code[code] = rows[-1]
        for row in rows:
            alias = row[5]
            if alias:
                target = by_code.get(alias[1])
                if target:
                    row[1], row[2], row[3] = target[1], target[2], target[3]
                else:
                    row[4] = 'error_alias_target_missing'
        return [tuple(row[:5]) for row in rows]

    def _write_files(self, directory, results, review_rows):
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / 'rite_names_import_result.tsv', 'w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle, delimiter='\t')
            writer.writerow(['cantus_feast_code', 'ecatalogus_uuid', 'ecatalogus_legacy_id', 'name', 'status'])
            writer.writerows(results)
        with open(directory / 'rite_names_skipped_review.tsv', 'w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle, delimiter='\t')
            writer.writerow(['cantus_feast_code', 'target_name_cantus', 'ecatalogus_uuid', 'ecatalogus_current_name'])
            writer.writerows(review_rows)
        self.stdout.write(f'Wrote {directory / "rite_names_import_result.tsv"} ({len(results)} codes) and '
                          f'{directory / "rite_names_skipped_review.tsv"} ({len(review_rows)} rows).')

    def _execute(self, operations, report):
        failed_keys = set()
        self.created_pk = {}
        for kind, key, values, bucket, entry in operations:
            if key in failed_keys:
                continue
            try:
                with transaction.atomic():
                    if kind == 'create':
                        rite = RiteNames(**values)
                        rite.save()
                        self.created_pk[key] = rite.pk
                        continue
                    rite = RiteNames.objects.get(pk=key)
                    for name, value in values.items():
                        setattr(rite, name, value)
                    rite.save()
            except IntegrityError as exc:
                failed_keys.add(key)
                items = getattr(report, bucket)
                if entry in items:
                    items.remove(entry)
                report.db_rejected.append(f'{entry} — refused by the database: {exc.args[-1]}')

    def _report(self, path, row_count, report, apply, verbosity):
        write = self.stdout.write
        mode = 'APPLY' if apply else 'DRY RUN'
        write(f'[{mode}] {path}: {row_count} row(s)')
        write(f'Created:                     {len(report.created)}')
        write(f'Renamed:                     {len(report.renamed)}')
        write(f'Updated without rename:      {len(report.updated)}')
        write(f'Unchanged (already applied): {len(report.unchanged)}')
        write(f'Skipped REVIEW_UPDATE:       {len(report.review_skipped)} (similar to an existing rite; for a human)')
        write(f'Duplicate codes -> same rite: {len(report.aliases)}')
        write(f'Skipped SKIP_TECHNICAL:      {len(report.technical_skipped)}')
        write(f'Skipped with error:          {len(report.skipped_with_error)}')

        sections = (
            ('No rite with the given uuid', report.missing_uuid, True),
            ('Current name does not match the plan', report.name_mismatch, True),
            ('Name collision', report.name_collision, True),
            ('Cantus code conflict', report.code_conflict, True),
            ('Refused by the database (unique name/code)', report.db_rejected, True),
            ('Invalid row', report.invalid, True),
            ('Same feast listed twice in Cantus', report.aliases, True),
            ('Verified-different pairs', report.pairs, True),
            ('english_translation shortened', report.truncated, True),
            ('Confirmed codes that are not REVIEW_UPDATE rows', report.confirmed_unused, True),
            ('Renamed', report.renamed, verbosity >= 2),
            ('Updated without rename', report.updated, verbosity >= 2),
            ('Skipped REVIEW_UPDATE', report.review_skipped, verbosity >= 2),
            ('Created', report.created, verbosity >= 3),
        )
        for title, items, show in sections:
            if not items or not show:
                continue
            write(f'\n{title} ({len(items)}):')
            for item in items:
                write(f'  {item}')
