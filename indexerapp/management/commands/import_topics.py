import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError
from indexerapp.models import Topic, Sections

class Command(BaseCommand):
    help = 'Imports or updates Topic data from a TSV file, handling self-referential parent_id'

    def add_arguments(self, parser):
        parser.add_argument('tsv_file', type=str, help='Path to the TSV file')

    def handle(self, *args, **options):
        tsv_file_path = options['tsv_file']
        try:
            # Read and sort data by id
            with open(tsv_file_path, newline='', encoding='utf-8') as tsvfile:
                reader = csv.DictReader(tsvfile, delimiter='\t')
                sorted_rows = sorted(reader, key=lambda x: int(x['id']) if x['id'] else float('inf'))

            # First Pass: Create or update records without parent
            for row in sorted_rows:
                try:
                    with transaction.atomic():
                        # Get Section instance by name
                        section_name = row['section']
                        section_instance = None
                        if section_name:
                            try:
                                section_instance = Sections.objects.get(name=section_name)
                            except Sections.DoesNotExist:
                                self.stdout.write(self.style.ERROR(
                                    f"Section with name '{section_name}' not found for row {row}"
                                ))
                                continue

                        # Convert votive to boolean
                        votive = row['votive'] == '1' if row['votive'] else None

                        # Check if Topic exists by id
                        topic_id = row['id'] if row.get('id') else None
                        if not topic_id:
                            self.stdout.write(self.style.ERROR(
                                f"No id provided for row {row}"
                            ))
                            continue

                        try:
                            topic = Topic.objects.get(id=topic_id)
                            created = False
                        except Topic.DoesNotExist:
                            try:
                                topic = Topic.objects.create(
                                    id=topic_id,
                                    name=row['name'] if row['name'] else None,
                                    section=section_instance,
                                    votive=votive
                                )
                                created = True
                            except IntegrityError as e:
                                self.stdout.write(self.style.ERROR(
                                    f"Cannot create Topic with id '{topic_id}': {e}"
                                ))
                                continue

                        if not created:
                            # Update existing record
                            topic.name = row['name'] if row['name'] else None
                            topic.section = section_instance
                            topic.votive = votive
                            topic.save()
                            self.stdout.write(self.style.WARNING(
                                f"Updated Topic with id '{topic_id}'"
                            ))
                        else:
                            self.stdout.write(self.style.SUCCESS(
                                f"Created Topic with id '{topic_id}'"
                            ))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing row {row} in first pass: {e}"))
                    continue

            # Second Pass: Update parent relationships
            for row in sorted_rows:
                try:
                    with transaction.atomic():
                        topic_id = row['id'] if row.get('id') else None
                        parent_id = row['parent_id'] if row['parent_id'] else None
                        if not topic_id or not parent_id:
                            continue

                        try:
                            topic = Topic.objects.get(id=topic_id)
                        except Topic.DoesNotExist:
                            self.stdout.write(self.style.ERROR(
                                f"Topic with id '{topic_id}' not found for parent update in row {row}"
                            ))
                            continue

                        try:
                            parent = Topic.objects.get(id=parent_id)
                            topic.parent = parent
                            topic.save()
                            self.stdout.write(self.style.SUCCESS(
                                f"Set parent for Topic id '{topic_id}' to parent_id '{parent_id}'"
                            ))
                        except Topic.DoesNotExist:
                            self.stdout.write(self.style.ERROR(
                                f"Parent with id '{parent_id}' not found for Topic id '{topic_id}' in row {row}"
                            ))
                            continue

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error updating parent for row {row}: {e}"))
                    continue

            self.stdout.write(self.style.SUCCESS('Finished importing/updating Topic data'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))