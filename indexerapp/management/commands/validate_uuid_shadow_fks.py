from django.core.management.base import BaseCommand, CommandError

from etlapp.uuid_fk import iter_models_with_uuid_shadow_fks, resolve_shadow_uuid


class Command(BaseCommand):
    help = 'Validates UUID shadow columns for sync-tracked ForeignKey fields that already have <field>_uuid columns.'

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
            '--fail-on-issues',
            action='store_true',
            help='Exit with a command error if missing or mismatched shadow UUIDs are found.',
        )

    def handle(self, *args, **options):
        chunk_size = options['chunk_size']
        issues_found = False

        try:
            model_specs = list(
                iter_models_with_uuid_shadow_fks(
                    model_names=options['models'],
                    categories=options['categories'],
                )
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        for model, specs in model_specs:
            queryset = model.objects.all().order_by('pk')
            if specs:
                queryset = queryset.select_related(*[field.name for _legacy_name, field in specs])

            field_counters = {
                field.attname: {'missing': 0, 'mismatch': 0, 'stale_without_fk': 0}
                for _legacy_name, field in specs
            }

            for instance in queryset.iterator(chunk_size=chunk_size):
                for _legacy_name, field in specs:
                    current_shadow_uuid = getattr(instance, field.attname)
                    expected_uuid = resolve_shadow_uuid(instance, field)

                    if getattr(instance, field.attname) is None:
                        if current_shadow_uuid is not None:
                            field_counters[field.attname]['stale_without_fk'] += 1
                        continue

                    if current_shadow_uuid is None:
                        field_counters[field.attname]['missing'] += 1
                        continue

                    if current_shadow_uuid != expected_uuid:
                        field_counters[field.attname]['mismatch'] += 1

            for legacy_name, field in specs:
                counters = field_counters[field.attname]
                total_issues = counters['missing'] + counters['mismatch'] + counters['stale_without_fk']
                if total_issues:
                    issues_found = True
                    status = 'ISSUES'
                else:
                    status = 'OK'

                self.stdout.write(
                    f'{model.__name__}.{legacy_name}: status={status} '
                    f'missing_shadow={counters["missing"]} '
                    f'mismatch={counters["mismatch"]} '
                    f'stale_without_fk={counters["stale_without_fk"]}'
                )

        if issues_found and options['fail_on_issues']:
            raise CommandError('UUID shadow FK validation failed.')

        if issues_found:
            self.stdout.write(self.style.WARNING('UUID shadow FK validation completed with issues.'))
            return

        self.stdout.write(self.style.SUCCESS('UUID shadow FK validation passed for all selected models.'))