import csv
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models

from etlapp.model_categories import MODEL_CATEGORIES, SYNC_CATEGORIES, get_model_category, get_sync_model_names


def build_sync_dependency_graph(indexer_models):
    sync_model_names = set(get_sync_model_names())
    graph = {}

    for model in indexer_models:
        dependencies = set()
        for field in model._meta.concrete_fields:
            if not isinstance(field, models.ForeignKey):
                continue

            related_model = field.related_model
            if related_model is None or related_model._meta.app_label != 'indexerapp':
                continue
            if related_model.__name__ == model.__name__:
                continue
            if related_model.__name__ not in sync_model_names:
                continue

            dependencies.add(related_model.__name__)

        graph[model.__name__] = sorted(dependencies)

    return graph


def assign_dependency_batches(graph):
    remaining = {model_name: set(dependencies) for model_name, dependencies in graph.items()}
    resolved = set()
    batches = {}
    batch_index = 0

    while remaining:
        ready = sorted(
            model_name
            for model_name, dependencies in remaining.items()
            if dependencies.issubset(resolved)
        )
        if not ready:
            for model_name in remaining:
                batches[model_name] = 'cycle'
            break

        for model_name in ready:
            batches[model_name] = str(batch_index)
            resolved.add(model_name)
            remaining.pop(model_name)

        batch_index += 1

    return batches


class Command(BaseCommand):
    help = 'Exports ETL model categories and sync metadata inventory to TSV.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='etl_model_categories.tsv',
            help='Output TSV file path (default: etl_model_categories.tsv)',
        )

    def handle(self, *args, **options):
        output_path = options['output']
        rows = []
        indexer_models = list(apps.get_app_config('indexerapp').get_models())
        dependency_graph = build_sync_dependency_graph(indexer_models)
        dependency_batches = assign_dependency_batches(dependency_graph)

        for model in indexer_models:
            meta = model._meta
            fields = [field for field in meta.get_fields() if getattr(field, 'concrete', False)]
            fk_fields = [
                field.name for field in fields
                if isinstance(field, models.ForeignKey)
            ]
            m2m_fields = [
                field.name for field in meta.many_to_many
            ]
            category = get_model_category(model.__name__)

            rows.append({
                'app_label': meta.app_label,
                'model_name': model.__name__,
                'db_table': meta.db_table,
                'category': category,
                'sync_enabled': 'yes' if category in SYNC_CATEGORIES else 'no',
                'has_uuid_field': 'yes' if any(field.name == 'uuid' for field in fields) else 'no',
                'has_entry_date_field': 'yes' if any(field.name == 'entry_date' for field in fields) else 'no',
                'has_version_field': 'yes' if any(field.name == 'version' for field in fields) else 'no',
                'has_sync_status_field': 'yes' if any(field.name == 'sync_status' for field in fields) else 'no',
                'foreign_keys': ','.join(fk_fields),
                'many_to_many': ','.join(m2m_fields),
                'sync_fk_dependencies': ','.join(dependency_graph.get(model.__name__, [])),
                'dependency_batch': dependency_batches.get(model.__name__, ''),
                'declared_in_plan': 'yes' if model.__name__ in MODEL_CATEGORIES else 'no',
            })

        rows.sort(key=lambda row: (row['category'], row['model_name']))

        with open(output_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    'app_label',
                    'model_name',
                    'db_table',
                    'category',
                    'sync_enabled',
                    'has_uuid_field',
                    'has_entry_date_field',
                    'has_version_field',
                    'has_sync_status_field',
                    'foreign_keys',
                    'many_to_many',
                    'sync_fk_dependencies',
                    'dependency_batch',
                    'declared_in_plan',
                ],
                delimiter='\t',
            )
            writer.writeheader()
            writer.writerows(rows)

        unassigned = [row['model_name'] for row in rows if row['category'] == 'unassigned']
        if unassigned:
            self.stdout.write(self.style.WARNING(f'Unassigned models: {", ".join(unassigned)}'))

        self.stdout.write(self.style.SUCCESS(f'Exported {len(rows)} models to {output_path}'))
