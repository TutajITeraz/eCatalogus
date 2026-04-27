import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from etlapp.services import build_delta_export_payload, build_manuscript_export_payload


def _parse_since(value):
    if not value:
        return None

    parsed = parse_datetime(value)
    if parsed is None:
        parsed_date = parse_date(value)
        if parsed_date is not None:
            parsed = timezone.datetime.combine(parsed_date, timezone.datetime.min.time())

    if parsed is None:
        raise CommandError(f'Invalid --since value: {value}')

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class Command(BaseCommand):
    help = 'Exports ETL category data to a JSON bundle file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            choices=['main', 'shared', 'ms'],
            required=True,
            help='ETL category to export.',
        )
        parser.add_argument(
            '--output',
            required=True,
            help='Output JSON file path.',
        )
        parser.add_argument(
            '--since',
            help='Optional ISO datetime/date lower bound for main/shared export.',
        )
        parser.add_argument(
            '--manuscript-uuid',
            help='Required only for --category ms. Exports one manuscript package.',
        )

    def handle(self, *args, **options):
        category = options['category']
        output_path = options['output']
        since = _parse_since(options.get('since'))
        manuscript_uuid = options.get('manuscript_uuid')

        if category == 'ms':
            if since is not None:
                raise CommandError('--since is not supported for --category ms.')
            if not manuscript_uuid:
                raise CommandError('--manuscript-uuid is required for --category ms.')
            payload = build_manuscript_export_payload(manuscript_uuid)
        else:
            if manuscript_uuid:
                raise CommandError('--manuscript-uuid is only supported for --category ms.')
            payload = build_delta_export_payload(category, since=since)

        with open(output_path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write('\n')

        self.stdout.write(
            self.style.SUCCESS(
                f'Exported category={category} model_count={payload.get("model_count", 0)} '
                f'record_count={payload.get("record_count", 0)} to {output_path}'
            )
        )