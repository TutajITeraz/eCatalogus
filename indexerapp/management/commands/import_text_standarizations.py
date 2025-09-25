import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError
from indexerapp.models import TextStandarization

class Command(BaseCommand):
    help = 'Imports or updates TextStandarization data from a TSV file'

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
                            # Get usu_id, handling empty values
                            usu_id = row['usu_id'] if row['usu_id'] else None

                            # Get other fields, handling empty values
                            cantus_id = row['cantus_id'] if row['cantus_id'] else None
                            standard_incipit = row['standard_incipit'] if row['standard_incipit'] else None
                            standard_full_text = row['standard_full_text'] if row['standard_full_text'] else None

                            # Check if TextStandarization exists by usu_id
                            if usu_id:
                                try:
                                    text_standarization, created = TextStandarization.objects.get_or_create(
                                        usu_id=usu_id,
                                        defaults={
                                            'cantus_id': cantus_id,
                                            'co_no': None,
                                            'formula': None,
                                            'standard_incipit': standard_incipit,
                                            'standard_full_text': standard_full_text
                                        }
                                    )
                                except IntegrityError as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Integrity error for usu_id '{usu_id}': {e}"
                                    ))
                                    continue
                            else:
                                # Handle null usu_id (create new record)
                                try:
                                    text_standarization = TextStandarization.objects.create(
                                        usu_id=None,
                                        cantus_id=cantus_id,
                                        co_no=None,
                                        formula=None,
                                        standard_incipit=standard_incipit,
                                        standard_full_text=standard_full_text
                                    )
                                    created = True
                                except IntegrityError as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot create TextStandarization with null usu_id: {e}"
                                    ))
                                    continue

                            if not created:
                                # Update existing record
                                text_standarization.cantus_id = cantus_id
                                text_standarization.co_no = None
                                text_standarization.formula = None
                                text_standarization.standard_incipit = standard_incipit
                                text_standarization.standard_full_text = standard_full_text
                                text_standarization.save()
                                self.stdout.write(self.style.WARNING(
                                    f"Updated TextStandarization with usu_id '{usu_id or 'null'}'"
                                ))
                            else:
                                self.stdout.write(self.style.SUCCESS(
                                    f"Created TextStandarization with usu_id '{usu_id or 'null'}'"
                                ))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing row {row}: {e}"))
                        continue
                self.stdout.write(self.style.SUCCESS('Finished importing/updating TextStandarization data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))