import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError
from indexerapp.models import MassHour, Type

class Command(BaseCommand):
    help = 'Imports or updates MassHour data from a TSV file, mapping type to Type.short_name'

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
                            # Get Type instance based on type short_name
                            type_short_name = row['type']
                            type_instance = None
                            if type_short_name:
                                try:
                                    type_instance = Type.objects.get(short_name=type_short_name)
                                except Type.DoesNotExist:
                                    self.stdout.write(self.style.ERROR(
                                        f"Type with short_name '{type_short_name}' not found for row {row}"
                                    ))
                                    continue

                            # Check if MassHour exists by id
                            mass_hour_id = row['id'] if row.get('id') else None
                            if not mass_hour_id:
                                self.stdout.write(self.style.ERROR(
                                    f"No id provided for row {row}"
                                ))
                                continue

                            try:
                                mass_hour = MassHour.objects.get(id=mass_hour_id)
                                created = False
                            except MassHour.DoesNotExist:
                                # Create new record if id doesn't exist
                                try:
                                    mass_hour = MassHour.objects.create(
                                        id=mass_hour_id,
                                        short_name=row['short_name'],
                                        name=row['name'],
                                        type=type_instance
                                    )
                                    created = True
                                except IntegrityError as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot create MassHour with id '{mass_hour_id}': {e}"
                                    ))
                                    continue

                            if not created:
                                # Check for unique constraint violations before updating
                                if (row['short_name'] != mass_hour.short_name and
                                        MassHour.objects.filter(short_name=row['short_name']).exists()):
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot update id '{mass_hour_id}' because short_name '{row['short_name']}' is already used"
                                    ))
                                    continue
                                if (row['name'] != mass_hour.name and
                                        MassHour.objects.filter(name=row['name']).exists()):
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot update id '{mass_hour_id}' because name '{row['name']}' is already used"
                                    ))
                                    continue

                                # Update existing record
                                mass_hour.short_name = row['short_name']
                                mass_hour.name = row['name']
                                mass_hour.type = type_instance
                                mass_hour.save()
                                self.stdout.write(self.style.WARNING(
                                    f"Updated MassHour with id '{mass_hour_id}'"
                                ))
                            else:
                                self.stdout.write(self.style.SUCCESS(
                                    f"Created MassHour with id '{mass_hour_id}'"
                                ))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing row {row}: {e}"))
                        continue
                self.stdout.write(self.style.SUCCESS('Finished importing/updating MassHour data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))