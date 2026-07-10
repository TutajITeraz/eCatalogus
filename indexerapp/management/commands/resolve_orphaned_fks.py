from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from etlapp.uuid_fk import iter_models_with_uuid_shadow_fks


class Command(BaseCommand):
    help = (
        'Finds FK references that point at a uuid no longer present in the target table '
        '(possible because these FKs use db_constraint=False) and, interactively per field, '
        'offers to null them out. Writes a .txt report of everything found/nulled, suitable '
        'for sending to the data contributors team.'
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
            help='Only report what would be found. Never prompts, never writes to the DB.',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Null every orphaned group without prompting (non-interactive).',
        )
        parser.add_argument(
            '--report-path',
            default=None,
            help='Where to write the .txt report. Defaults to orphaned_fk_report_<timestamp>.txt in the current directory.',
        )
        parser.add_argument(
            '--max-listed',
            type=int,
            default=200,
            help='Max rows listed per field in the report before truncating.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        auto_yes = options['yes']
        max_listed = options['max_listed']

        try:
            model_specs = list(
                iter_models_with_uuid_shadow_fks(
                    model_names=options['models'],
                    categories=options['categories'],
                )
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        report_sections = []
        total_orphans = 0
        total_nulled = 0
        any_found = False

        for model, specs in model_specs:
            for _legacy_name, field in specs:
                attname = field.attname
                relname = field.name
                target_model = field.related_model

                # relname__isnull short-circuits to checking the local column for a plain
                # FK, so it can't detect a non-null value with no matching target row.
                # Compare the raw stored value against the target's actual uuid set instead.
                valid_targets = target_model.objects.filter(uuid__isnull=False).values('uuid')
                orphan_qs = model.objects.filter(**{f'{attname}__isnull': False}).exclude(
                    **{f'{attname}__in': valid_targets}
                )
                count = orphan_qs.count()
                if count == 0:
                    continue

                any_found = True
                total_orphans += count

                model_field_names = {f.name for f in model._meta.fields}
                label_field = 'name' if 'name' in model_field_names else ('uuid' if 'uuid' in model_field_names else None)
                value_fields = ['pk', attname] + ([label_field] if label_field else [])
                rows = list(orphan_qs.order_by('pk').values(*value_fields))

                self.stdout.write(
                    f"{model.__name__}.{relname} -> {target_model.__name__}: "
                    f"{count} orphaned reference(s) found"
                )

                do_null = False
                if dry_run:
                    pass
                elif auto_yes:
                    do_null = True
                else:
                    answer = input(
                        f"  Null out these {count} reference(s) on {model.__name__}.{relname}? "
                        f"[y]es / [n]o / [l]ist then decide: "
                    ).strip().lower()
                    if answer == 'l':
                        self._print_rows(rows, attname, label_field, max_listed)
                        answer = input(f"  Null out these {count} reference(s)? [y/N]: ").strip().lower()
                    do_null = answer == 'y'

                header = (
                    f"{model.__name__}.{relname} -> {target_model.__name__} "
                    f"({count} rows, {'NULLED' if do_null else 'left as-is'})"
                )
                section = [header, '-' * len(header)]
                for row in rows[:max_listed]:
                    label = row.get(label_field, '') if label_field else ''
                    section.append(f"  pk={row['pk']} {label_field or ''}={label!r} dangling_{attname}={row[attname]}")
                if count > max_listed:
                    section.append(f"  ... and {count - max_listed} more (rerun with --model {model.__name__} to see all)")
                report_sections.append('\n'.join(section))

                if do_null:
                    updated = orphan_qs.update(**{attname: None})
                    total_nulled += updated
                    self.stdout.write(self.style.WARNING(f"  Nulled {updated} row(s)."))

        if not any_found:
            self.stdout.write(self.style.SUCCESS('No orphaned FK references found.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"Dry run: found {total_orphans} orphaned reference(s) across the FKs above. Nothing was changed."
            ))

        report_path = options['report_path'] or f"orphaned_fk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        header_lines = [
            f"Orphaned FK reference report - generated {datetime.now(timezone.utc).isoformat()}",
            f"Total orphaned references found: {total_orphans}",
            f"Total nulled this run: {total_nulled}",
            "",
        ]
        with open(report_path, 'w') as report_file:
            report_file.write('\n'.join(header_lines))
            report_file.write('\n\n'.join(report_sections))
            report_file.write('\n')

        self.stdout.write(self.style.SUCCESS(f"Report written to {report_path}"))

    def _print_rows(self, rows, attname, label_field, max_listed):
        for row in rows[:max_listed]:
            label = row.get(label_field, '') if label_field else ''
            self.stdout.write(f"    pk={row['pk']} {label_field or ''}={label!r} dangling_{attname}={row[attname]}")
        if len(rows) > max_listed:
            self.stdout.write(f"    ... and {len(rows) - max_listed} more")
