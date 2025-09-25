import csv
from django.core.management.base import BaseCommand
from indexerapp.models import Type

class Command(BaseCommand):
    help = 'Imports Type data from a TSV file'

    def add_arguments(self, parser):
        parser.add_argument('tsv_file', type=str, help='Path to the TSV file')

    def handle(self, *args, **options):
        tsv_file_path = options['tsv_file']
        try:
            with open(tsv_file_path, newline='', encoding='utf-8') as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter='\t')  # Tab delimiter
                for row in reader:
                    try:
                        Type.objects.create(
                            short_name=row['short_name'],
                            name=row['name']
                        )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error importing row {row}: {e}"))
                self.stdout.write(self.style.SUCCESS('Successfully imported Type data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))