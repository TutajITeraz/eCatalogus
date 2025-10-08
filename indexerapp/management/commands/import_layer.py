import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from indexerapp.models import Layer

class Command(BaseCommand):
    help = 'Imports or updates Layer data from a TSV file, handling id'

    def add_arguments(self, parser):
        parser.add_argument('tsv_file', type=str, help='Path to the TSV file')

    def handle(self, *args, **options):
        tsv_file_path = options['tsv_file']
        try:
            with open(tsv_file_path, newline='', encoding='utf-8') as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter='\t')  # Tab delimiter
                with transaction.atomic():  # Ensure atomicity for updates
                    for row in reader:
                        try:
                            # Check if Layer exists by short_name
                            layer, created = Layer.objects.get_or_create(
                                short_name=row['short_name'],
                                defaults={
                                    'name': row['name'],
                                    'id': row['id'] if row.get('id') else None
                                }
                            )

                            if not created:
                                # Update existing record
                                layer.name = row['name']
                                if row.get('id'):
                                    layer.id = row['id']
                                layer.save()
                                self.stdout.write(self.style.WARNING(
                                    f"Updated Layer with short_name '{row['short_name']}'"
                                ))
                            else:
                                self.stdout.write(self.style.SUCCESS(
                                    f"Created Layer with short_name '{row['short_name']}'"
                                ))

                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Error processing row {row}: {e}"))
                self.stdout.write(self.style.SUCCESS('Finished importing/updating Layer data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))