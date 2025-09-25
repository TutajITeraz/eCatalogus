import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError
from indexerapp.models import Genre, Type, Layer

class Command(BaseCommand):
    help = 'Imports or updates Genre data from a TSV file, appending types and layers by id'

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
                            # Get Type instances based on type short_name (single or comma-separated)
                            type_short_names = row['type'].split(',') if row['type'] else []
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

                            # Get Layer instances based on layer short_name (single or comma-separated)
                            layer_short_names = row['layer'].split(',') if row['layer'] else []
                            layer_instances = []
                            for layer_short_name in layer_short_names:
                                layer_short_name = layer_short_name.strip()
                                if layer_short_name:
                                    try:
                                        layer_instance = Layer.objects.get(short_name=layer_short_name)
                                        layer_instances.append(layer_instance)
                                    except Layer.DoesNotExist:
                                        self.stdout.write(self.style.ERROR(
                                            f"Layer with short_name '{layer_short_name}' not found for row {row}"
                                        ))
                                        continue

                            # Check if Genre exists by id
                            genre_id = row['id'] if row.get('id') else None
                            if not genre_id:
                                self.stdout.write(self.style.ERROR(
                                    f"No id provided for row {row}"
                                ))
                                continue

                            try:
                                genre = Genre.objects.get(id=genre_id)
                                created = False
                            except Genre.DoesNotExist:
                                # Create new record if id doesn't exist
                                try:
                                    genre = Genre.objects.create(
                                        id=genre_id,
                                        short_name=row['short_name'],
                                        name=row['name']
                                    )
                                    created = True
                                except IntegrityError as e:
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot create Genre with id '{genre_id}': {e}"
                                    ))
                                    continue

                            if not created:
                                # Check for unique constraint violations before updating
                                if (row['short_name'] != genre.short_name and
                                        Genre.objects.filter(short_name=row['short_name']).exists()):
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot update id '{genre_id}' because short_name '{row['short_name']}' is already used"
                                    ))
                                    continue
                                if (row['name'] != genre.name and
                                        Genre.objects.filter(name=row['name']).exists()):
                                    self.stdout.write(self.style.ERROR(
                                        f"Cannot update id '{genre_id}' because name '{row['name']}' is already used"
                                    ))
                                    continue

                                # Update short_name and name
                                genre.short_name = row['short_name']
                                genre.name = row['name']
                                genre.save()
                                self.stdout.write(self.style.WARNING(
                                    f"Updated Genre with id '{genre_id}'"
                                ))

                            # Append to ManyToManyFields
                            for type_instance in type_instances:
                                if type_instance not in genre.types.all():
                                    genre.types.add(type_instance)
                            for layer_instance in layer_instances:
                                if layer_instance not in genre.layers.all():
                                    genre.layers.add(layer_instance)

                            if type_instances or layer_instances:
                                self.stdout.write(self.style.SUCCESS(
                                    f"Appended types {type_short_names} and layers {layer_short_names} to Genre with id '{genre_id}'"
                                ))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing row {row}: {e}"))
                        continue
                self.stdout.write(self.style.SUCCESS('Finished importing/updating Genre data'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"TSV file not found: {tsv_file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing TSV file: {e}"))