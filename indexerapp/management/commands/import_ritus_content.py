"""Import a ritus-indexer project export (CSV) as manuscript content.

The ritus indexer exports one row per indexed item, with the manuscript it
belongs to repeated in ``project_id`` / ``project_name``. This command groups
the rows by manuscript name: a manuscript that already exists has its content
replaced, a manuscript that does not exist yet is created first.

Usage::

    python manage.py import_ritus_content ritus_eclla_projects.csv
    python manage.py import_ritus_content ritus_eclla_projects.csv --dry-run
"""

import csv
import re
import sys
from collections import OrderedDict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from indexerapp.models import (
    Content,
    ContentFunctions,
    Contributors,
    Day,
    EditionContent,
    Formulas,
    Genre,
    Layer,
    LiturgicalGenres,
    ManuscriptMusicNotations,
    Manuscripts,
    MassHour,
    Quires,
    RiteNames,
    SeasonMonth,
    Sections,
    TextStandarization,
    Week,
)

#: The export can carry a whole folio of transcribed text in one cell.
csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))

#: How a manuscript with several ritus projects under the same name is resolved.
DUPLICATE_STRATEGIES = ('richest', 'first', 'last', 'merge')

#: `Formulas` and `RiteNames` keep the same numeric id on every instance
#: (etlapp.services.MODELS_WITH_STABLE_ID), so the ids the ritus indexer
#: exports can be resolved as primary keys. Every other dictionary is matched
#: by a human-readable key instead, because ids are instance-local there.
STABLE_ID_LOOKUPS = {
    'formula_id': Formulas,
    'rite_id': RiteNames,
}


def normalize_name(value):
    """Collapse the stray newlines and double spaces the export contains."""
    return re.sub(r'\s+', ' ', (value or '')).strip()


def clean(value):
    value = (value or '').strip()
    return value or None


def as_int(value):
    value = clean(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def as_float(value):
    value = clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_bool(value):
    value = (value or '').strip().lower()
    if value in ('1', 'true', 't', 'yes', 'y', 'tak'):
        return True
    if value in ('0', 'false', 'f', 'no', 'n', 'nie'):
        return False
    return None


def as_original_or_added(value):
    value = (value or '').strip().upper()
    if value.startswith('ORIG'):
        return 'ORIGINAL'
    if value.startswith('ADD'):
        return 'ADDED'
    return None


class Command(BaseCommand):
    help = (
        'Import a ritus-indexer CSV export. Rows are grouped by manuscript name: '
        'an existing manuscript has its content replaced, a missing one is created.'
    )

    def add_arguments(self, parser):
        parser.add_argument('csv_file', help='Path to the ritus-indexer CSV export')
        parser.add_argument(
            '--delimiter', default=',',
            help="Column separator of the export (default ','; use $'\\t' for TSV)",
        )
        parser.add_argument(
            '--encoding', default='utf-8-sig',
            help='File encoding (default utf-8-sig, which also accepts a plain UTF-8 file)',
        )
        parser.add_argument(
            '--only', action='append', default=[], metavar='NAME',
            help='Import only this manuscript name; repeatable',
        )
        parser.add_argument(
            '--duplicate-projects', choices=DUPLICATE_STRATEGIES, default='richest',
            help=(
                'What to do when several ritus projects share one manuscript name: '
                'richest (most rows, the default), first, last, or merge them all'
            ),
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change and roll everything back',
        )

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.unresolved = OrderedDict()

        rows = self.read_rows(options)
        groups = self.group_by_manuscript(rows, options)

        if not groups:
            raise CommandError('The export contains no usable rows.')

        created = replaced = 0
        for name, project_rows in groups.items():
            was_created = self.import_manuscript(name, project_rows)
            if was_created:
                created += 1
            else:
                replaced += 1

        self.report_unresolved()
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if self.dry_run else ""}'
            f'{created} manuscript(s) created, {replaced} replaced, '
            f'{sum(len(r) for r in groups.values())} content row(s) written.'
        ))

    def read_rows(self, options):
        try:
            handle = open(options['csv_file'], newline='', encoding=options['encoding'])
        except OSError as exc:
            raise CommandError(f'Cannot open {options["csv_file"]}: {exc}')

        with handle as csv_file:
            reader = csv.DictReader(csv_file, delimiter=options['delimiter'])
            if not reader.fieldnames or 'project_name' not in reader.fieldnames:
                raise CommandError(
                    'The file has no "project_name" column - is it a ritus-indexer export, '
                    'and is --delimiter right?'
                )
            return [row for row in reader if normalize_name(row.get('project_name'))]

    def group_by_manuscript(self, rows, options):
        """Bucket rows by manuscript name, resolving same-name ritus projects."""
        only = {normalize_name(name) for name in options['only']}

        by_name = OrderedDict()
        for row in rows:
            name = normalize_name(row.get('project_name'))
            if only and name not in only:
                continue
            by_name.setdefault(name, OrderedDict()).setdefault(
                clean(row.get('project_id')) or '', []
            ).append(row)

        strategy = options['duplicate_projects']
        groups = OrderedDict()
        for name, by_project in by_name.items():
            if len(by_project) == 1:
                groups[name] = next(iter(by_project.values()))
                continue

            counts = ', '.join(f'{pid or "?"}={len(rows)} rows' for pid, rows in by_project.items())
            if strategy == 'merge':
                chosen_id, chosen = 'all', [r for rows in by_project.values() for r in rows]
            elif strategy == 'first':
                chosen_id, chosen = next(iter(by_project.items()))
            elif strategy == 'last':
                chosen_id, chosen = next(reversed(by_project.items()))
            else:
                chosen_id, chosen = max(by_project.items(), key=lambda item: len(item[1]))

            self.stdout.write(self.style.WARNING(
                f'  ! "{name}" is exported as {len(by_project)} ritus projects ({counts}); '
                f'--duplicate-projects={strategy} keeps project {chosen_id}'
            ))
            groups[name] = chosen

        return groups

    # ------------------------------------------------------------------ #

    def import_manuscript(self, name, rows):
        matches = list(Manuscripts.objects.filter(name=name)[:2])
        if len(matches) > 1:
            self.stdout.write(self.style.ERROR(
                f'  ! "{name}" matches more than one manuscript - skipped, resolve by hand'
            ))
            return False

        with transaction.atomic():
            if matches:
                manuscript, was_created = matches[0], False
            else:
                manuscript, was_created = Manuscripts.objects.create(name=name), True

            removed, _ = Content.objects.filter(manuscript_uuid=manuscript.uuid).delete()
            for row in rows:
                self.create_content(manuscript, row)

            verb = 'created' if was_created else 'replaced'
            self.stdout.write(
                f'  {verb}: "{name}" - {len(rows)} row(s) in'
                + (f', {removed} object(s) removed' if removed else '')
            )

            if self.dry_run:
                transaction.set_rollback(True)

        return was_created

    def create_content(self, manuscript, row):
        content = Content(
            manuscript_uuid=manuscript,
            formula_uuid=self.lookup_stable_id(row, 'formula_id'),
            rubric_uuid=self.lookup_rubric(row),
            rubric_name_from_ms=clean(row.get('rite_name_from_ms')),
            subrubric_name_from_ms=clean(row.get('subrite_name_from_ms')),
            rubric_sequence=as_int(row.get('rite_sequence_in_the_MS')),
            formula_text=clean(row.get('formula_text_from_ms')),
            sequence_in_ms=as_int(row.get('sequence_in_ms')),
            where_in_ms_from=(clean(row.get('where_in_ms_from')) or '')[:32],
            where_in_ms_to=(clean(row.get('where_in_ms_to')) or '')[:32],
            digital_page_number=as_int(row.get('digital_page_number')),
            original_or_added=as_original_or_added(row.get('original_or_added')),
            liturgical_genre_uuid=self.lookup_by_pk(LiturgicalGenres, row, 'liturgical_genre_id'),
            quire_uuid=self.lookup_by_pk(Quires, row, 'quire_id'),
            section_uuid=self.lookup_by_pk(Sections, row, 'section_id'),
            subsection_uuid=self.lookup_by_pk(Sections, row, 'subsection_id'),
            music_notation_uuid=self.lookup_by_pk(ManuscriptMusicNotations, row, 'music_notation_id'),
            function_uuid=self.lookup_by_pk(ContentFunctions, row, 'function_id'),
            subfunction_uuid=self.lookup_by_pk(ContentFunctions, row, 'subfunction_id'),
            biblical_reference=(clean(row.get('biblical_reference')) or None),
            reference_to_other_items=(clean(row.get('reference_to_other_items')) or None),
            similarity_by_user=self.lookup_similarity_by_user(row),
            proper_texts=as_bool(row.get('proper_texts')),
            similarity_levenshtein=as_float(row.get('levenshtein')),
            data_contributor_uuid=self.lookup_by_pk(Contributors, row, 'contributor_id'),
            edition_index_uuid=self.lookup_by_pk(EditionContent, row, 'edition_index'),
            edition_subindex=clean(row.get('edition_subindex')),
            comments=clean(row.get('comments')),
            text_standarization_uuid=self.lookup_named(
                TextStandarization, row, 'text_standarization__usu_id', 'usu_id'),
            layer_uuid=self.lookup_short_name(Layer, row, 'layer'),
            mass_hour_uuid=self.lookup_short_name(MassHour, row, 'mass_hour'),
            genre_uuid=self.lookup_short_name(Genre, row, 'genre'),
            season_month_uuid=self.lookup_short_name(SeasonMonth, row, 'season_month'),
            week_uuid=self.lookup_short_name(Week, row, 'week'),
            day_uuid=self.lookup_short_name(Day, row, 'day'),
        )
        # Content.save() recomputes the Levenshtein distance against the linked
        # formula and fans out the digital page number to layouts and quires,
        # so the rows go in one by one rather than through bulk_create.
        content.save()

    # -------------------------- dictionary lookups -------------------- #

    def note_unresolved(self, column, value):
        self.unresolved.setdefault(column, set()).add(value)

    def lookup_stable_id(self, row, column):
        """Resolve an id the ritus indexer shares with us (formulas, rite names)."""
        value = as_int(row.get(column))
        if value is None:
            return None
        instance = STABLE_ID_LOOKUPS[column].objects.filter(pk=value).first()
        if instance is None:
            self.note_unresolved(column, value)
        return instance

    def lookup_by_pk(self, model, row, column):
        value = as_int(row.get(column))
        if value is None:
            return None
        instance = model.objects.filter(pk=value).first()
        if instance is None:
            self.note_unresolved(column, value)
        return instance

    def lookup_named(self, model, row, column, field):
        value = clean(row.get(column))
        if value is None:
            return None
        instance = model.objects.filter(**{field: value}).first()
        if instance is None:
            self.note_unresolved(column, value)
        return instance

    def lookup_short_name(self, model, row, column):
        """Usuarium-style dictionaries are keyed by short_name, with name as fallback."""
        value = clean(row.get(column))
        if value is None:
            return None
        instance = (
            model.objects.filter(short_name=value).first()
            or model.objects.filter(name=value).first()
        )
        if instance is None:
            self.note_unresolved(column, value)
        return instance

    def lookup_rubric(self, row):
        return (
            self.lookup_stable_id(row, 'rite_id')
            or self.lookup_named(RiteNames, row, 'rite_name_standarized', 'name')
        )

    def lookup_similarity_by_user(self, row):
        value = clean(row.get('similarity_by_user'))
        if value is None:
            return None
        valid = {choice for choice, _label in Content._meta.get_field('similarity_by_user').choices}
        if value not in valid:
            self.note_unresolved('similarity_by_user', value)
            return None
        return value

    def report_unresolved(self):
        for column, values in self.unresolved.items():
            shown = sorted(str(value) for value in values)
            preview = ', '.join(shown[:10]) + (', ...' if len(shown) > 10 else '')
            self.stdout.write(self.style.WARNING(
                f'  ! {len(shown)} unknown value(s) for "{column}", left empty: {preview}'
            ))
