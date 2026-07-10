from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from etlapp.uuid_fk import iter_models_with_uuid_shadow_fks


class Command(BaseCommand):
    help = (
        'Some instances carry real FK constraints on the sync *_uuid columns that Django '
        'does not manage (models declare db_constraint=False, but a constraint from before '
        'that was set, or added by hand, can still be sitting in the database). Those block '
        "Django's own AlterField/migration DDL and drift independently per instance. This "
        'command finds and (optionally) drops them, so a later migration can add a single, '
        'Django-tracked constraint per column instead. MySQL/MariaDB only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            action='append',
            dest='models',
            help='Limit to this indexerapp model name. Can be passed multiple times.',
        )
        parser.add_argument(
            '--category',
            action='append',
            dest='categories',
            help='Limit to ETL categories: main, shared, ms.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report what would be dropped.',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Drop every unmanaged constraint found without prompting.',
        )

    def handle(self, *args, **options):
        if connection.vendor != 'mysql':
            raise CommandError(f"This command only supports MySQL/MariaDB, got vendor={connection.vendor!r}.")

        dry_run = options['dry_run']
        auto_yes = options['yes']

        try:
            model_specs = list(
                iter_models_with_uuid_shadow_fks(
                    model_names=options['models'],
                    categories=options['categories'],
                )
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        found_any = False
        dropped = 0

        with connection.cursor() as cur:
            for model, specs in model_specs:
                table = model._meta.db_table
                for _legacy_name, field in specs:
                    column = field.column
                    cur.execute(
                        """
                        SELECT CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                        FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                          AND COLUMN_NAME = %s
                          AND REFERENCED_TABLE_NAME IS NOT NULL
                        """,
                        [table, column],
                    )
                    constraints = cur.fetchall()

                    for constraint_name, ref_table, ref_column in constraints:
                        found_any = True
                        self.stdout.write(
                            f"{table}.{column}: found unmanaged FK constraint "
                            f"'{constraint_name}' -> {ref_table}.{ref_column}"
                        )

                        do_drop = False
                        if dry_run:
                            pass
                        elif auto_yes:
                            do_drop = True
                        else:
                            answer = input(f"  Drop constraint '{constraint_name}'? [y/N]: ").strip().lower()
                            do_drop = answer == 'y'

                        if do_drop:
                            cur.execute(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{constraint_name}`")
                            dropped += 1
                            self.stdout.write(self.style.WARNING(f"  Dropped '{constraint_name}'."))

        if not found_any:
            self.stdout.write(self.style.SUCCESS('No unmanaged legacy FK constraints found.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Dry run: found unmanaged legacy FK constraints listed above. None were dropped.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"Dropped {dropped} legacy FK constraint(s)."))
