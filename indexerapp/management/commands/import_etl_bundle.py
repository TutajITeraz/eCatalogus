import json

from django.core.management.base import BaseCommand, CommandError

from etlapp.services import import_delta_payload, import_manuscript_payload


class Command(BaseCommand):
    help = 'Imports an ETL JSON bundle file through the existing ETL service pipeline.'

    def add_arguments(self, parser):
        parser.add_argument('input_file', help='Path to the input JSON bundle file.')

    def handle(self, *args, **options):
        input_file = options['input_file']

        try:
            with open(input_file, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
        except FileNotFoundError as exc:
            raise CommandError(f'Input file not found: {input_file}') from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f'Input file is not valid JSON: {input_file}') from exc

        if not isinstance(payload, dict):
            raise CommandError('Input JSON must be an object.')

        category = payload.get('category')
        if category in {'main', 'shared'}:
            summary = import_delta_payload(category, payload)
        elif category == 'ms':
            summary = import_manuscript_payload(payload)
        else:
            raise CommandError(f'Unsupported or missing bundle category: {category}')

        self.stdout.write(self.style.SUCCESS(json.dumps(summary, ensure_ascii=False, indent=2)))