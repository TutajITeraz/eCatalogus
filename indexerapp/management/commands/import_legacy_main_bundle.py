import json

from django.core.management.base import BaseCommand, CommandError

from etlapp.services import import_delta_payload


class Command(BaseCommand):
    help = 'Imports a legacy main bootstrap bundle into the current instance.'

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
        if payload.get('category') != 'main':
            raise CommandError('Legacy main bundle must have category=main.')

        shared_dependencies = payload.get('shared_dependencies', [])
        shared_summary = None
        if shared_dependencies:
            shared_summary = import_delta_payload('shared', {'models': shared_dependencies})

        summary = import_delta_payload('main', payload)
        if shared_summary is not None:
            summary['shared_dependencies'] = shared_summary
        self.stdout.write(self.style.SUCCESS(json.dumps(summary, ensure_ascii=False, indent=2)))