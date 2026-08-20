"""Surveys the `main` vocabularies for columns that could carry a unique constraint.

Three "XII 3/4" datings and three bare "Germany" places got in because nothing
stopped an editor from typing a name the table already had. A unique constraint
is the cheap fix, but it cannot be added blind: the migration fails on data that
already violates it, and a column that is empty half the time is not an identity
in the first place.

So this reports, per candidate column: how much of it is filled, how many values
collide today, and whether the column can physically carry a unique index. What
the database would consider a collision is decided by its collation, which is
usually case-insensitive — that is exactly the rule the constraint would
enforce, so the count is taken from the database rather than from Python. A
second, stricter count in Python (trimmed and case-folded) shows the near-misses
the constraint would still let through, because "Poland " and "Poland" are
worth knowing about even when the database calls them different.

Nothing is written. This produces a decision sheet, not a migration.
"""

import json
from collections import Counter

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from etlapp.model_categories import get_model_category


TEXT_FIELD_TYPES = {'CharField', 'TextField'}

# InnoDB caps an index key at 3072 bytes with DYNAMIC row format, and utf8mb4
# spends up to 4 bytes per character.
MAX_INDEX_BYTES = 3072
BYTES_PER_CHAR = 4

MAX_EXAMPLE_LENGTH = 60

# Below this many filled rows the distinct-to-filled ratio says nothing: a
# four-row vocabulary with one duplicate scores 0.75 and would be dismissed as
# categorical. Small tables therefore skip that test and get judged on their
# duplicates alone — reporting a categorical column for review is a cheap
# mistake, hiding a broken identity is not.
MIN_ROWS_FOR_CATEGORICAL = 20


def _iter_main_models(requested_names=None):
    requested = set(requested_names or [])
    models = [
        model for model in apps.get_app_config('indexerapp').get_models()
        if get_model_category(model.__name__) == 'main'
    ]

    unknown = requested.difference({model.__name__ for model in models})
    if unknown:
        raise CommandError('Not main-category indexerapp models: ' + ', '.join(sorted(unknown)))

    return [model for model in models if not requested or model.__name__ in requested]


def _candidate_fields(model):
    for field in model._meta.concrete_fields:
        if field.primary_key or field.name == 'uuid':
            continue
        if field.is_relation:
            continue
        if field.get_internal_type() not in TEXT_FIELD_TYPES:
            continue
        yield field


def _index_feasibility(field):
    """Whether a plain UniqueConstraint on this column is even expressible."""
    if field.get_internal_type() == 'TextField':
        return {
            'feasible': False,
            'reason': 'TextField needs a prefix index, which UniqueConstraint cannot express',
        }

    max_length = field.max_length or 0
    if max_length * BYTES_PER_CHAR > MAX_INDEX_BYTES:
        return {
            'feasible': False,
            'reason': f'max_length={max_length} exceeds the {MAX_INDEX_BYTES}-byte index key limit under utf8mb4',
        }

    return {'feasible': True, 'reason': ''}


def _truncate(value):
    text = str(value)
    if len(text) > MAX_EXAMPLE_LENGTH:
        text = f'{text[:MAX_EXAMPLE_LENGTH - 1]}…'
    return text.replace('\t', ' ').replace('\n', ' ')


def _analyse_field(model, field, example_limit):
    name = field.name
    total = model.objects.count()

    nulls = model.objects.filter(**{f'{name}__isnull': True}).count()
    blanks = model.objects.filter(**{name: ''}).count()
    filled = total - nulls - blanks

    populated = model.objects.exclude(**{f'{name}__isnull': True}).exclude(**{name: ''})

    collisions = (
        populated.values(name)
        .annotate(row_count=Count('pk'))
        .filter(row_count__gt=1)
        .order_by('-row_count', name)
    )

    duplicate_groups = 0
    duplicate_rows = 0
    examples = []
    for group in collisions:
        duplicate_groups += 1
        duplicate_rows += group['row_count']
        if len(examples) < example_limit:
            examples.append({'value': _truncate(group[name]), 'count': group['row_count']})

    # The stricter, whitespace- and case-insensitive view: collisions a unique
    # index would NOT catch but a human would call the same thing.
    normalised_counter = Counter()
    for value in populated.values_list(name, flat=True).iterator(chunk_size=2000):
        normalised_counter[' '.join(str(value).split()).casefold()] += 1
    normalised_groups = sum(1 for count in normalised_counter.values() if count > 1)

    distinct = populated.values(name).distinct().count()

    return {
        'field': name,
        'type': field.get_internal_type(),
        'max_length': field.max_length,
        'rows': total,
        'nulls': nulls,
        'blanks': blanks,
        'filled': filled,
        'fill_ratio': round(filled / total, 4) if total else 0.0,
        'distinct': distinct,
        'distinct_ratio': round(distinct / filled, 4) if filled else 0.0,
        'duplicate_groups': duplicate_groups,
        'duplicate_rows': duplicate_rows,
        'normalised_duplicate_groups': normalised_groups,
        'examples': examples,
        **_index_feasibility(field),
    }


def _verdict(analysis, min_fill, min_distinct):
    if not analysis['feasible']:
        return 'not-indexable'
    if analysis['rows'] == 0:
        return 'empty-table'
    if analysis['fill_ratio'] < min_fill:
        return 'too-sparse'
    if analysis['filled'] >= MIN_ROWS_FOR_CATEGORICAL and analysis['distinct_ratio'] < min_distinct:
        # "Poland" appearing 27 times in Places.country_today_eng is the data
        # being correct, not duplicated. A column that repeats by design is not
        # an identity and must never carry a unique constraint.
        return 'categorical'
    if analysis['blanks']:
        # A unique index tolerates many NULLs but not many empty strings.
        return 'needs-cleanup'
    if analysis['duplicate_groups']:
        return 'needs-cleanup'
    return 'ready'


class Command(BaseCommand):
    help = 'Reports which main-category columns could carry a unique constraint, and what blocks the rest.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            action='append',
            dest='models',
            help='Limit the survey to one main model. Can be passed multiple times.',
        )
        parser.add_argument(
            '--min-fill',
            type=float,
            default=0.9,
            help='Ignore columns filled in less than this fraction of rows. 0 surveys everything. Default 0.9.',
        )
        parser.add_argument(
            '--min-distinct',
            type=float,
            default=0.9,
            help=(
                'Below this distinct-to-filled ratio a column is reported as categorical rather '
                'than as a broken identity. Default 0.9.'
            ),
        )
        parser.add_argument(
            '--examples',
            type=int,
            default=3,
            help='Colliding values to show per column. Default 3.',
        )
        parser.add_argument('--json', action='store_true', help='Emit the survey as JSON.')
        parser.add_argument('--tsv', help='Write one row per surveyed column to this path as TSV.')
        parser.add_argument(
            '--emit-constraints',
            action='store_true',
            help='Print a ready-to-paste Meta.constraints line for every column that is ready today.',
        )

    def handle(self, *args, **options):
        models = _iter_main_models(options.get('models'))
        min_fill = options['min_fill']

        survey = []
        for model in models:
            columns = []
            for field in _candidate_fields(model):
                analysis = _analyse_field(model, field, options['examples'])
                analysis['verdict'] = _verdict(analysis, min_fill, options['min_distinct'])
                columns.append(analysis)

            survey.append({
                'model': model._meta.label,
                'name': model.__name__,
                'rows': model.objects.count(),
                'columns': columns,
            })

        if options['tsv']:
            self._write_tsv(options['tsv'], survey)

        if options['json']:
            self.stdout.write(json.dumps(survey, ensure_ascii=False, indent=2, default=str))
            return None

        self._write_human_report(survey, min_fill, options['emit_constraints'])
        return None

    def _write_tsv(self, path, survey):
        lines = [
            'model\tfield\ttype\tmax_length\trows\tfilled\tfill_ratio\tdistinct\tdistinct_ratio\t'
            'duplicate_groups\tduplicate_rows\tnormalised_duplicate_groups\tnulls\tblanks\tverdict\treason'
        ]
        for entry in survey:
            for column in entry['columns']:
                lines.append(
                    f'{entry["name"]}\t{column["field"]}\t{column["type"]}\t{column["max_length"] or ""}\t'
                    f'{column["rows"]}\t{column["filled"]}\t{column["fill_ratio"]}\t{column["distinct"]}\t'
                    f'{column["distinct_ratio"]}\t'
                    f'{column["duplicate_groups"]}\t{column["duplicate_rows"]}\t'
                    f'{column["normalised_duplicate_groups"]}\t{column["nulls"]}\t{column["blanks"]}\t'
                    f'{column["verdict"]}\t{column["reason"]}'
                )

        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(lines) + '\n')

        self.stdout.write(f'Wrote {len(lines) - 1} column(s) to {path}')

    def _write_human_report(self, survey, min_fill, emit_constraints):
        ready = []
        needs_cleanup = []

        for entry in survey:
            shown = [column for column in entry['columns'] if column['verdict'] != 'too-sparse']
            hidden = len(entry['columns']) - len(shown)

            if not shown and not hidden:
                continue

            self.stdout.write(f'{entry["name"]} ({entry["rows"]} rows)')

            for column in shown:
                length_suffix = f'({column["max_length"]})' if column['max_length'] else ''
                self.stdout.write(
                    f'  {column["field"]:<28} {column["type"]}'
                    f'{length_suffix} '
                    f'filled={column["filled"]}/{column["rows"]} '
                    f'distinct={column["distinct"]} ({column["distinct_ratio"]:.0%}) '
                    f'dup_groups={column["duplicate_groups"]} dup_rows={column["duplicate_rows"]} '
                    f'blanks={column["blanks"]} -> {column["verdict"].upper()}'
                )

                if column['reason']:
                    self.stdout.write(f'      {column["reason"]}')

                if column['verdict'] == 'categorical':
                    self.stdout.write('      repeats by design, not an identity column')
                    continue

                for example in column['examples']:
                    self.stdout.write(f'      "{example["value"]}" x{example["count"]}')

                extra_normalised = column['normalised_duplicate_groups'] - column['duplicate_groups']
                if extra_normalised > 0:
                    self.stdout.write(
                        f'      + {extra_normalised} more group(s) collide only after trimming and '
                        f'case-folding — a unique index would NOT catch those'
                    )

                if column['verdict'] == 'ready':
                    ready.append((entry['name'], column['field']))
                elif column['verdict'] == 'needs-cleanup':
                    needs_cleanup.append((entry['name'], column['field'], column['duplicate_groups'], column['blanks']))

            if hidden:
                self.stdout.write(
                    f'  ({hidden} column(s) filled in less than {min_fill:.0%} of rows, hidden — '
                    f'lower --min-fill to see them)'
                )

        self.stdout.write('')
        self.stdout.write(f'Ready for a unique constraint today: {len(ready)}')
        for model_name, field_name in ready:
            self.stdout.write(f'  {model_name}.{field_name}')

        self.stdout.write(f'Blocked until the data is cleaned: {len(needs_cleanup)}')
        for model_name, field_name, groups, blanks in needs_cleanup:
            blocker = []
            if groups:
                blocker.append(f'{groups} duplicate group(s)')
            if blanks:
                blocker.append(f'{blanks} empty-string row(s)')
            self.stdout.write(f'  {model_name}.{field_name}: {" and ".join(blocker)}')

        if emit_constraints and ready:
            self.stdout.write('')
            self.stdout.write('Paste into each model\'s Meta:')
            for model_name, field_name in ready:
                self.stdout.write(
                    f'  # {model_name}\n'
                    f'  constraints = [models.UniqueConstraint('
                    f'fields=["{field_name}"], name="{model_name.lower()}_{field_name}_uniq")]'
                )
