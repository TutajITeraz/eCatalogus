import json
from datetime import timedelta

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category


DESCRIPTION_MAX_LENGTH = 90


class Command(BaseCommand):
    help = (
        'Lists indexerapp records whose entry_date falls inside a recent time window. '
        'Every synced model stamps entry_date with auto_now and the ETL import writes the '
        'source value back verbatim, so this covers both local edits and records pulled from '
        'a peer. It cannot tell a create apart from an update - see logs/etl_import.log for that.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=float, default=24.0, help='Window size in hours (default: 24).')
        parser.add_argument('--since', help='ISO datetime/date lower bound. Overrides --hours when given.')
        parser.add_argument(
            '--model',
            action='append',
            dest='models',
            help='Restrict to a model name, e.g. Content. Can be passed multiple times.',
        )
        parser.add_argument(
            '--category',
            action='append',
            dest='categories',
            help='Restrict to an ETL category (main, shared, ms, local). Can be passed multiple times.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum rows printed per model (default: 50, 0 for unlimited).',
        )
        parser.add_argument('--summary', action='store_true', help='Print per-model counts only.')
        parser.add_argument('--json', action='store_true', dest='as_json', help='Emit JSON instead of a text table.')
        parser.add_argument(
            '--no-deletions',
            action='store_true',
            help='Skip the DeletedRecord tombstones that normally close the report.',
        )

    def handle(self, *args, **options):
        since = self._resolve_since(options)
        limit = options['limit']
        model_filter = {name.lower() for name in options.get('models') or []}
        category_filter = {name.lower() for name in options.get('categories') or []}

        report = {
            'since': since.isoformat(),
            'until': timezone.now().isoformat(),
            'models': [],
            'total': 0,
        }

        for model in self._iter_models(model_filter, category_filter):
            queryset = model.objects.filter(entry_date__gte=since).order_by('entry_date', 'pk')
            count = queryset.count()
            if not count:
                continue

            entry = {
                'model': model._meta.label,
                'category': get_model_category(model.__name__),
                'count': count,
                'records': [],
            }
            if not options['summary']:
                rows = queryset if limit <= 0 else queryset[:limit]
                entry['records'] = [self._describe(instance) for instance in rows]
                entry['truncated'] = 0 < limit < count

            report['models'].append(entry)
            report['total'] += count

        if not options['no_deletions']:
            report['deletions'] = self._collect_deletions(since, model_filter, category_filter, limit)

        if options['as_json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        self._render_text(report, summary_only=options['summary'])

    def _resolve_since(self, options):
        raw_since = options.get('since')
        if not raw_since:
            return timezone.now() - timedelta(hours=options['hours'])

        parsed = parse_datetime(raw_since)
        if parsed is None:
            parsed_date = parse_date(raw_since)
            if parsed_date is None:
                raise CommandError(f'Cannot parse --since value: {raw_since}')
            parsed = timezone.datetime.combine(parsed_date, timezone.datetime.min.time())

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def _iter_models(self, model_filter, category_filter):
        for model in sorted(apps.get_app_config('indexerapp').get_models(), key=lambda m: m._meta.label):
            if not any(field.name == 'entry_date' for field in model._meta.concrete_fields):
                continue
            if model_filter and model.__name__.lower() not in model_filter:
                continue
            if category_filter and get_model_category(model.__name__).lower() not in category_filter:
                continue
            yield model

    def _describe(self, instance):
        try:
            label = str(instance)
        except Exception as exc:  # A broken __str__ must not sink the whole report.
            label = f'<unprintable: {exc}>'

        if len(label) > DESCRIPTION_MAX_LENGTH:
            label = label[:DESCRIPTION_MAX_LENGTH - 1] + '…'

        return {
            'pk': instance.pk,
            'uuid': str(getattr(instance, 'uuid', '') or ''),
            'entry_date': instance.entry_date.isoformat() if instance.entry_date else None,
            'label': label,
        }

    def _collect_deletions(self, since, model_filter, category_filter, limit):
        deleted_record_model = apps.get_model('indexerapp', 'DeletedRecord')
        queryset = deleted_record_model.objects.filter(deleted_at__gte=since).order_by('deleted_at')
        if category_filter:
            queryset = queryset.filter(category__in=category_filter)

        records = [
            {
                'model_label': record.model_label,
                'category': record.category,
                'object_uuid': str(record.object_uuid),
                'source_pk': record.source_pk,
                'deleted_at': record.deleted_at.isoformat(),
            }
            for record in (queryset if limit <= 0 else queryset[:limit])
            if not model_filter or record.model_label.split('.')[-1].lower() in model_filter
        ]

        return {'count': queryset.count(), 'records': records}

    def _render_text(self, report, summary_only):
        self.stdout.write(self.style.MIGRATE_HEADING(f"Changes between {report['since']} and {report['until']}"))

        if not report['models']:
            self.stdout.write('  no records with entry_date in this window')
        else:
            for entry in report['models']:
                self.stdout.write('')
                self.stdout.write(
                    self.style.MIGRATE_LABEL(f"{entry['model']} [{entry['category']}] - {entry['count']} record(s)")
                )
                for record in entry['records']:
                    self.stdout.write(
                        f"    {record['entry_date']}  pk={record['pk']}  uuid={record['uuid']}  {record['label']}"
                    )
                if entry.get('truncated'):
                    self.stdout.write(f"    ... {entry['count'] - len(entry['records'])} more (raise --limit)")

        deletions = report.get('deletions')
        if deletions and deletions['count']:
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_LABEL(f"Deletions - {deletions['count']} tombstone(s)"))
            for record in deletions['records']:
                self.stdout.write(
                    f"    {record['deleted_at']}  {record['model_label']} [{record['category']}]  "
                    f"uuid={record['object_uuid']}  source_pk={record['source_pk']}"
                )

        self.stdout.write('')
        summary_suffix = ' (summary only)' if summary_only else ''
        self.stdout.write(self.style.SUCCESS(f"Total: {report['total']} changed record(s){summary_suffix}"))
