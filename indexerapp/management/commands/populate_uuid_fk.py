from django.core.management.base import BaseCommand, CommandError

from etlapp.uuid_fk import iter_models_with_uuid_shadow_fks, resolve_shadow_uuid


class Command(BaseCommand):
    help = 'Backfills UUID shadow columns for sync-tracked ForeignKey fields that already have <field>_uuid columns.'

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
        chunk_size = options['chunk_size']
        dry_run = options['dry_run']
        total_updated = 0

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

            model_updates = 0
            for instance in queryset.iterator(chunk_size=chunk_size):
                updates = {}
                for _legacy_name, field in specs:
                    expected_uuid = resolve_shadow_uuid(instance, field)
                    if getattr(instance, field.attname) != expected_uuid:
                        updates[field.attname] = expected_uuid

                if not updates:
                    continue

                model_updates += 1
                if not dry_run:
                    model.objects.filter(pk=instance.pk).update(**updates)

            total_updated += model_updates
            verb = 'would update' if dry_run else 'updated'
            self.stdout.write(f'{model.__name__}: {verb} {model_updates} rows')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run complete. No rows were updated.'))
            return

        self.stdout.write(self.style.SUCCESS(f'UUID FK shadow backfill complete. Updated {total_updated} rows.'))