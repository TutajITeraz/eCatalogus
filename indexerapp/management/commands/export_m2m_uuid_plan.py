import csv

from django.apps import apps
from django.core.management.base import BaseCommand

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category


class Command(BaseCommand):
    help = 'Exports an inventory of sync-tracked ManyToMany fields that need UUID migration planning.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='etl_uuid_m2m_plan.tsv',
            help='Output TSV file path (default: etl_uuid_m2m_plan.tsv)',
        )

    def handle(self, *args, **options):
        output_path = options['output']
        rows = []

        for model in apps.get_app_config('indexerapp').get_models():
            model_category = get_model_category(model.__name__)
            if model_category not in SYNC_CATEGORIES:
                continue

            for field in model._meta.many_to_many:
                related_model = field.related_model
                if related_model is None or related_model._meta.app_label != 'indexerapp':
                    continue

                related_category = get_model_category(related_model.__name__)
                if related_category not in SYNC_CATEGORIES:
                    continue

                through_model = field.remote_field.through
                rows.append({
                    'model_name': model.__name__,
                    'model_table': model._meta.db_table,
                    'model_category': model_category,
                    'm2m_field': field.name,
                    'related_model': related_model.__name__,
                    'related_table': related_model._meta.db_table,
                    'related_category': related_category,
                    'through_model': through_model.__name__,
                    'through_table': through_model._meta.db_table,
                    'through_auto_created': 'yes' if through_model._meta.auto_created else 'no',
                    'suggested_uuid_list_key': f'{field.name}_uuids',
                })

        rows.sort(key=lambda row: (row['model_category'], row['model_name'], row['m2m_field']))

        with open(output_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    'model_name',
                    'model_table',
                    'model_category',
                    'm2m_field',
                    'related_model',
                    'related_table',
                    'related_category',
                    'through_model',
                    'through_table',
                    'through_auto_created',
                    'suggested_uuid_list_key',
                ],
                delimiter='\t',
            )
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f'Exported {len(rows)} UUID M2M plan rows to {output_path}'))