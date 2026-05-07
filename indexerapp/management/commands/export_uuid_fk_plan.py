import csv

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category
from etlapp.uuid_fk import get_legacy_fk_aliases


class Command(BaseCommand):
    help = 'Exports an inventory of sync-tracked ForeignKey fields that need UUID shadow migration planning.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='etl_uuid_fk_plan.tsv',
            help='Output TSV file path (default: etl_uuid_fk_plan.tsv)',
        )

    def handle(self, *args, **options):
        output_path = options['output']
        rows = []

        for model in apps.get_app_config('indexerapp').get_models():
            model_category = get_model_category(model.__name__)
            if model_category not in SYNC_CATEGORIES:
                continue

            legacy_names_by_field = get_legacy_fk_aliases(model)

            for field in model._meta.concrete_fields:
                if not isinstance(field, models.ForeignKey):
                    continue

                related_model = field.related_model
                if related_model is None or related_model._meta.app_label != 'indexerapp':
                    continue

                related_category = get_model_category(related_model.__name__)
                if related_category not in SYNC_CATEGORIES:
                    continue

                legacy_name = legacy_names_by_field.get(field.name)
                if legacy_name is None and field.name.endswith('_uuid'):
                    legacy_name = field.name[:-5]
                if legacy_name is None:
                    continue

                related_has_uuid = any(
                    related_field.name == 'uuid'
                    for related_field in related_model._meta.concrete_fields
                )

                rows.append({
                    'model_name': model.__name__,
                    'model_table': model._meta.db_table,
                    'model_category': model_category,
                    'fk_field': legacy_name,
                    'fk_column': f'{legacy_name}_id',
                    'related_model': related_model.__name__,
                    'related_table': related_model._meta.db_table,
                    'related_category': related_category,
                    'related_has_uuid': 'yes' if related_has_uuid else 'no',
                    'nullable': 'yes' if field.null else 'no',
                    'suggested_uuid_field': field.name,
                    'suggested_uuid_column': field.column,
                })

        rows.sort(key=lambda row: (row['model_category'], row['model_name'], row['fk_field']))

        with open(output_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    'model_name',
                    'model_table',
                    'model_category',
                    'fk_field',
                    'fk_column',
                    'related_model',
                    'related_table',
                    'related_category',
                    'related_has_uuid',
                    'nullable',
                    'suggested_uuid_field',
                    'suggested_uuid_column',
                ],
                delimiter='\t',
            )
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f'Exported {len(rows)} UUID FK plan rows to {output_path}'))