import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError
from indexerapp.models import Ceremony

class Command(BaseCommand):
    help = 'Imports or updates Ceremony data from a TSV file'

    def add_arguments(self, parser):
        parser.add_argument('tsv_file', type=str, help='Path to the TSV file')

    def handle(self, *args, **options):
        tsv_file_path = options['tsv_file']
        try:
            with open(tsv_file_path, newline='', encoding='utf-8') as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter='\t')  # Tab delimiter
                for row in reader:
                    try:
                        with transaction.atomic():  # Atomic block per row
                            # Get name, handling empty values
                            name = row['name'] if row['name'] and row['name'] != '?' else None

                            # Check if Ceremony exists by name
                            if name:
                                try:
                                    ceremony, created = Ceremony.objects.get_or_create(
                                        name=name,
                                        defaults={
                                            'latin_keywords': row['latin_keywords'],
                                            'short_description': row['short_description']
                                        }
                                    )
                                except IntegrityError as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Integrity error for name '{name}': {e}"
                                    ))
                                    continue
                            else:
                                # Handle null name (create new record without checking name)
                                try:
                                    ceremony = Ceremony.objects.create(
                                        name=None,
                                        latin_keywords=row['latin_keywords'],
                                        short_description=row['short_description']
                                    )
                                    created = True
                                except IntegrityError as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot create Ceremony with null name: {e}"
                                    ))
                                    continue

                            if not created:
                                # Update existing record
                                ceremony.latin_keywords = row['latin_keywords']
                                ceremony.short_description = row['short_description']
                                ceremony.save()
                                self.stdout.write(self.style.WARNING(
                                    f"Updated Ceremony with name '{name or 'null'}'"
                                ))
                            else:
                                self.stdout.write(self.style.SUCCESS(
                                    f"Created Ceremony with name '{name or 'null'}'"
                                ))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing row {row}: {e}"))
                        continue
                self.stdout.write(self.style.SUCCESS('Finished importing/updating Ceremony data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))