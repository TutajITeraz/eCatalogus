import csv
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import models

RELATION_TYPES = {
    models.ForeignKey: 'ForeignKey',
    models.OneToOneField: 'OneToOneField',
    models.ManyToManyField: 'ManyToManyField',
}

class Command(BaseCommand):
    help = "Eksportuje podsumowanie wszystkich modeli i pól do CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="models_summary.csv",
            help="Nazwa pliku wyjściowego (domyślnie models_summary.csv)",
        )

    def handle(self, *args, **options):
        rows = []
        header = [
            "app_label",
            "model_name",
            "verbose_name_plural",
            "field_name",
            "verbose_name",
            "field_type",
            "null",
            "blank",
            "max_length",
            "choices",
            "related_model",
            "related_name",
            "relation_type",
            "help_text",
        ]
        rows.append(header)

        for model in apps.get_models():
            meta = model._meta
            app_label = meta.app_label
            model_name = model.__name__
            verbose_plural = (
                str(meta.verbose_name_plural).title()
                if meta.verbose_name_plural
                else ""
            )

            # Wiersz z informacją o modelu (pusty wiersz na pole)
            rows.append([app_label, model_name, verbose_plural] + [""] * 11)

            # Przechodzimy tylko po "konkretnych" polach (nie reverse, nie auto_created)
            for field in meta.get_fields():
                # Pomijamy relacje odwrotne i pola automatyczne (np. reverse FK, m2m reverse)
                if field.auto_created or field.is_relation and field.one_to_many or field.many_to_many and not field.concrete:
                    continue

                # Podstawowe informacje o polu
                field_name = field.name
                verbose_name = (
                    str(field.verbose_name).title()
                    if field.verbose_name
                    else field_name.replace("_", " ").title()
                )
                field_type = field.get_internal_type()

                null = field.null if hasattr(field, "null") else ""
                blank = field.blank if hasattr(field, "blank") else ""
                max_length = getattr(field, "max_length", "") or ""

                # Choices
                choices = ""
                if getattr(field, "choices", None) and field.choices:
                    choices = " | ".join([f"{k}: {v}" for k, v in field.choices])

                # Relacje
                related_model = ""
                related_name = ""
                relation_type = ""

                if field.is_relation:
                    # Dla zwykłych pól relacyjnych (FK, O2O, M2M) – mają related_model
                    if hasattr(field, "related_model") and field.related_model:
                        related_model = field.related_model._meta.object_name

                    # related_name istnieje tylko na polach "wielu" (czyli nie na reverse)
                    if hasattr(field, "related_name"):
                        related_name = field.related_name or "(domyślne)"

                    relation_type = RELATION_TYPES.get(type(field), "Inne")

                help_text = getattr(field, "help_text", "") or ""

                rows.append([
                    app_label,
                    model_name,
                    verbose_plural,
                    field_name,
                    verbose_name,
                    field_type,
                    null,
                    blank,
                    max_length,
                    choices,
                    related_model,
                    related_name,
                    relation_type,
                    help_text,
                ])

        filename = options["output"]
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(f"Gotowe! Zapisano {len(rows)-1} wierszy do pliku: {filename}")
        )