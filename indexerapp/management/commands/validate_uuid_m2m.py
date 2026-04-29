from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category


def iter_models_with_sync_m2m_fields(model_names=None, categories=None):
    requested_models = set(model_names or [])
    requested_categories = set(categories or [])

    invalid_categories = requested_categories.difference(SYNC_CATEGORIES)
    if invalid_categories:
        raise ValueError(
            'Unsupported categories for validate_uuid_m2m: '
            + ', '.join(sorted(invalid_categories))
        )

    available_model_names = {model.__name__ for model in apps.get_app_config('indexerapp').get_models()}
    invalid_models = requested_models.difference(available_model_names)
    if invalid_models:
        raise ValueError(
            'Unknown indexerapp models for validate_uuid_m2m: '
            + ', '.join(sorted(invalid_models))
        )

    for model in apps.get_app_config('indexerapp').get_models():
        model_category = get_model_category(model.__name__)
        if model_category not in SYNC_CATEGORIES:
            continue
        if requested_models and model.__name__ not in requested_models:
            continue
        if requested_categories and model_category not in requested_categories:
            continue

        fields = []
        for field in model._meta.many_to_many:
            related_model = field.related_model
            if related_model is None or related_model._meta.app_label != 'indexerapp':
                continue

            related_category = get_model_category(related_model.__name__)
            if related_category not in SYNC_CATEGORIES:
                continue

            fields.append(field)

        if fields:
            yield model, fields


class Command(BaseCommand):
    help = 'Validates sync-tracked ManyToMany relations for UUID readiness before UUID-only ETL lookups.'

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
            default=200,
            help='Iterator chunk size for queryset traversal.',
        )
        parser.add_argument(
            '--fail-on-issues',
            action='store_true',
            help='Exit with a command error if M2M UUID readiness issues are found.',
        )

    def handle(self, *args, **options):
        issues_found = False

        try:
            model_specs = list(
                iter_models_with_sync_m2m_fields(
                    model_names=options['models'],
                    categories=options['categories'],
                )
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        for model, fields in model_specs:
            queryset = model.objects.all().order_by('pk').prefetch_related(*[field.name for field in fields])

            field_counters = {
                field.name: {'owner_missing_uuid': 0, 'related_missing_uuid': 0, 'relations_checked': 0}
                for field in fields
            }

            for instance in queryset.iterator(chunk_size=options['chunk_size']):
                for field in fields:
                    related_objects = list(getattr(instance, field.name).all())
                    if not related_objects:
                        continue

                    field_counters[field.name]['relations_checked'] += len(related_objects)

                    if getattr(instance, 'uuid', None) is None:
                        field_counters[field.name]['owner_missing_uuid'] += 1

                    field_counters[field.name]['related_missing_uuid'] += sum(
                        1 for related_object in related_objects if getattr(related_object, 'uuid', None) is None
                    )

            for field in fields:
                counters = field_counters[field.name]
                total_issues = counters['owner_missing_uuid'] + counters['related_missing_uuid']
                status = 'ISSUES' if total_issues else 'OK'
                if total_issues:
                    issues_found = True

                self.stdout.write(
                    f'{model.__name__}.{field.name}: status={status} '
                    f'relations_checked={counters["relations_checked"]} '
                    f'owner_missing_uuid={counters["owner_missing_uuid"]} '
                    f'related_missing_uuid={counters["related_missing_uuid"]}'
                )

        if issues_found and options['fail_on_issues']:
            raise CommandError('UUID M2M validation failed.')

        if issues_found:
            self.stdout.write(self.style.WARNING('UUID M2M validation completed with issues.'))
            return

        self.stdout.write(self.style.SUCCESS('UUID M2M validation passed for all selected models.'))