"""Load Cantus Index melodies into the Melody table from a TSV file.

Columns: melody_id, cantus_id, genre, mode, volpiano, source, source_url (header
required, any order; only melody_id and volpiano are mandatory). Parsed with a real
CSV reader, so ``source`` may span lines. Entries whose melody_id contains
``.node%3A`` are broken Cantus exports: skipped and listed. Empty cantus_id,
genre, mode, source and source_url are stored as NULL. Rows are matched by ``melody_id``; a second run changes nothing. UUIDs are
derived from the melody id, so every instance gets the same one. Dry run
(writes nothing, still reports) with ``--dry-run``. The whole file is one
transaction, so a bad file leaves the table as it was.
"""

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from etlapp.main_guard import MainReadOnlyError, assert_main_writable
from etlapp.uuid_utils import build_deterministic_sync_uuid
from indexerapp.models import Melody


REQUIRED = ('melody_id', 'volpiano')
BROKEN_ID = '.node%3A'


class _DryRunRollback(Exception):
    pass


class Command(BaseCommand):
    help = 'Imports Cantus melodies (melody_id, cantus_id, volpiano, source_url) from a TSV file.'

    def add_arguments(self, parser):
        parser.add_argument('tsv_file')
        parser.add_argument('--dry-run', action='store_true', help='Report only; roll everything back.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if not dry_run:
            try:
                assert_main_writable('Melody', subject='Melodies')
            except MainReadOnlyError as exc:
                raise CommandError(str(exc))
        try:
            with open(options['tsv_file'], newline='', encoding='utf-8') as handle:
                reader = csv.DictReader(handle, delimiter='\t')
                missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
                if missing:
                    raise CommandError(f'Header is missing column(s): {", ".join(missing)}.')
                rows = [(reader.line_num, row) for row in reader]
        except OSError as exc:
            raise CommandError(str(exc))

        created, updated, unchanged, errors, skipped = 0, 0, 0, [], []
        seen = set()
        id_max = Melody._meta.get_field('melody_id').max_length
        try:
            with transaction.atomic():
                for line, row in rows:
                    melody_id = (row.get('melody_id') or '').strip()
                    volpiano = (row.get('volpiano') or '').strip()
                    if BROKEN_ID in melody_id:
                        skipped.append(f'line {line}: {melody_id} (broken Cantus entry)')
                        continue
                    cantus_id = (row.get('cantus_id') or '').strip() or None
                    source_url = (row.get('source_url') or '').strip() or None
                    if not melody_id or len(melody_id) > id_max:
                        errors.append(f'line {line}: empty or too long melody_id "{melody_id}"')
                        continue
                    if melody_id in seen:
                        errors.append(f'line {line}: {melody_id} repeated in the file; later row ignored')
                        continue
                    seen.add(melody_id)
                    if cantus_id and len(cantus_id) > 32:
                        errors.append(f'line {line}: {melody_id}: cantus_id too long')
                        continue
                    wanted = {
                        'volpiano': volpiano, 'cantus_id': cantus_id, 'source_url': source_url,
                        'genre': (row.get('genre') or '').strip() or None,
                        'mode': (row.get('mode') or '').strip() or None,
                        'source': (row.get('source') or '').strip() or None,
                    }
                    melody = Melody.objects.filter(melody_id=melody_id).first()
                    if melody is None:
                        Melody.objects.create(
                            melody_id=melody_id,
                            uuid=build_deterministic_sync_uuid('indexerapp.Melody', melody_id),
                            **wanted,
                        )
                        created += 1
                        continue
                    changed = [k for k, v in wanted.items() if getattr(melody, k) != v]
                    if melody.uuid is None:
                        melody.uuid = build_deterministic_sync_uuid('indexerapp.Melody', melody_id)
                        changed.append('uuid')
                    if not changed:
                        unchanged += 1
                        continue
                    for key, value in wanted.items():
                        setattr(melody, key, value)
                    melody.save()
                    updated += 1
                if dry_run:
                    raise _DryRunRollback
        except _DryRunRollback:
            pass

        self.stdout.write(f'[{"DRY RUN" if dry_run else "APPLY"}] {options["tsv_file"]}: {len(rows)} row(s)')
        self.stdout.write(f'Created: {created}  Updated: {updated}  Unchanged: {unchanged}  Skipped: {len(skipped)}  Errors: {len(errors)}')
        for message in skipped:
            self.stdout.write(f'  skipped {message}')
        for message in errors:
            self.stdout.write(f'  {message}')
