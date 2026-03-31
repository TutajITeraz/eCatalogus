import uuid

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category, get_sync_model_names


class Command(BaseCommand):
    help = 'Backfills UUIDs for sync-tracked models without invoking model save hooks.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            action='append',
            dest='models',
            help='Specific indexerapp model name to process. Can be passed multiple times.',
        )
        parser.add_argument(
            '--category',
            action='append',
            dest='categories',
            help='Limit processing to ETL categories: main, shared, ms.',
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=500,
            help='Iterator chunk size for queryset traversal.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report how many rows would be updated without modifying the database.',
        )

    def handle(self, *args, **options):
        selected_models = options['models'] or self._get_models_for_categories(options['categories'])
        valid_models = set(get_sync_model_names())
        invalid_models = sorted(set(selected_models) - valid_models)
        if invalid_models:
            raise CommandError(f'Unknown or non-sync models: {", ".join(invalid_models)}')

        chunk_size = options['chunk_size']
        dry_run = options['dry_run']
        total_updated = 0

        for model_name in selected_models:
            model = apps.get_model('indexerapp', model_name)
            queryset = model.objects.filter(uuid__isnull=True).only('pk')
            missing_count = queryset.count()

            if dry_run:
                self.stdout.write(f'{model_name}: would update {missing_count} rows')
                continue

            updated = 0
            for instance in queryset.iterator(chunk_size=chunk_size):
                model.objects.filter(pk=instance.pk, uuid__isnull=True).update(uuid=uuid.uuid4())
                updated += 1

            total_updated += updated
            self.stdout.write(self.style.SUCCESS(f'{model_name}: updated {updated} rows'))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run complete. No rows were updated.'))
            return

        self.stdout.write(self.style.SUCCESS(f'UUID backfill complete. Updated {total_updated} rows in total.'))

    def _get_models_for_categories(self, categories):
        if not categories:
            return get_sync_model_names()

        invalid_categories = sorted(set(categories) - SYNC_CATEGORIES)
        if invalid_categories:
            raise CommandError(f'Unknown ETL categories: {", ".join(invalid_categories)}')

        return [
            model_name
            for model_name in get_sync_model_names()
            if get_model_category(model_name) in categories
        ]