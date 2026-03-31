from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category, get_sync_model_names


class Command(BaseCommand):
    help = 'Validates UUID coverage and duplicate UUIDs for sync-tracked models.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            action='append',
            dest='models',
            help='Specific indexerapp model name to validate. Can be passed multiple times.',
        )
        parser.add_argument(
            '--category',
            action='append',
            dest='categories',
            help='Limit validation to ETL categories: main, shared, ms.',
        )
        parser.add_argument(
            '--fail-on-issues',
            action='store_true',
            help='Exit with a command error if missing or duplicate UUIDs are found.',
        )

    def handle(self, *args, **options):
        selected_models = options['models'] or self._get_models_for_categories(options['categories'])
        valid_models = set(get_sync_model_names())
        invalid_models = sorted(set(selected_models) - valid_models)
        if invalid_models:
            raise CommandError(f'Unknown or non-sync models: {", ".join(invalid_models)}')

        issues_found = False

        for model_name in selected_models:
            model = apps.get_model('indexerapp', model_name)
            missing_count = model.objects.filter(uuid__isnull=True).count()
            duplicate_groups = list(
                model.objects.exclude(uuid__isnull=True)
                .values('uuid')
                .annotate(total=Count('uuid'))
                .filter(total__gt=1)
            )
            duplicate_count = len(duplicate_groups)

            if missing_count or duplicate_count:
                issues_found = True

            status = 'OK'
            if missing_count or duplicate_count:
                status = 'ISSUES'

            self.stdout.write(
                f'{model_name}: status={status} missing_uuid={missing_count} duplicate_uuid_groups={duplicate_count}'
            )

        if issues_found and options['fail_on_issues']:
            raise CommandError('UUID integrity validation failed.')

        if issues_found:
            self.stdout.write(self.style.WARNING('UUID integrity validation completed with issues.'))
            return

        self.stdout.write(self.style.SUCCESS('UUID integrity validation passed for all selected models.'))

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