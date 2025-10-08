import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError
from indexerapp.models import Week, Type

class Command(BaseCommand):
    help = 'Imports or updates Week data from a TSV file, mapping types to Type.short_name'

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
                            # Get Type instances based on comma-separated type short_names
                            type_short_names = row['types'].split(',') if row['types'] else []
                            type_instances = []
                            for type_short_name in type_short_names:
                                type_short_name = type_short_name.strip()
                                if type_short_name:
                                    try:
                                        type_instance = Type.objects.get(short_name=type_short_name)
                                        type_instances.append(type_instance)
                                    except Type.DoesNotExist:
                                        self.stdout.write(self.style.ERROR(
                                            f"Type with short_name '{type_short_name}' not found for row {row}"
                                        ))
                                        continue

                            # Check if Week exists by short_name
                            try:
                                week, created = Week.objects.get_or_create(
                                    short_name=row['short_name'],
                                    defaults={
                                        'name': row['name'],
                                        'id': row['id'] if row.get('id') else None
                                    }
                                )
                            except IntegrityError as e:
                                if 'name' in str(e).lower():
                                    self.stdout.write(self.style.ERROR(
                                        f"Duplicate name '{row['name']}' for short_name '{row['short_name']}' in row {row}"
                                    ))
                                else:
                                    self.stdout.write(self.style.ERROR(
                                        f"Integrity error for short_name '{row['short_name']}': {e}"
                                    ))
                                continue

                            if not created:
                                # Check if new name would cause a duplicate
                                if Week.objects.filter(name=row['name']).exclude(short_name=row['short_name']).exists():
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot update short_name '{row['short_name']}' because name '{row['name']}' is already used by another Week"
                                    ))
                                    continue

                                # Update existing record
                                week.name = row['name']
                                if row.get('id'):
                                    try:
                                        week.id = row['id']
                                    except IntegrityError as e:
                                        self.stdout.write(self.style.WARNING(
                                            f"Could not set id '{row['id']}' for short_name '{row['short_name']}': {e}"
                                        ))
                                week.save()
                                # Update ManyToManyField
                                week.types.clear()  # Clear existing relationships
                                week.types.add(*type_instances)  # Add new relationships
                                self.stdout.write(self.style.WARNING(
                                    f"Updated Week with short_name '{row['short_name']}'"
                                ))
                            else:
                                # Set ManyToManyField for new record
                                week.types.add(*type_instances)
                                self.stdout.write(self.style.SUCCESS(
                                    f"Created Week with short_name '{row['short_name']}'"
                                ))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing row {row}: {e}"))
                        continue
                self.stdout.write(self.style.SUCCESS('Finished importing/updating Week data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))