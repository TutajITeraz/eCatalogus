import csv
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import models

RELATION_TYPES = {
    models.ForeignKey: 'FK',
    models.OneToOneField: 'O2O',
    models.ManyToManyField: 'M2M',
}

class Command(BaseCommand):
    help = "Eksportuje wszystkie modele Django do CSV z pełnym opisem pól"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='models_summary.csv',
            help='Nazwa pliku wyjściowego CSV'
        )

    def handle(self, *args, **options):
        rows = []
        header = [
            "app_label", "model_name", "verbose_name_plural",
            "field_name", "verbose_name", "field_type",
            "can_be_null", "can_be_blank", "max_length",
            "choices", "related_model", "related_name", "relation_type", "comments"
        ]
        rows.append(header)

        for model in apps.get_models():
            app_label = model._meta.app_label
            model_name = model.__name__
            verbose_plural = model._meta.verbose_name_plural.title() if model._meta.verbose_name_plural else ""

            # Najpierw dodaj wiersz z informacją o modelu (bez pola)
            rows.append([
                app_label, model_name, verbose_plural,
                "", "", "", "", "", "", "", "", "", "", ""
            ])

            for field in model._meta.get_fields():
                if field.auto_created or field.is_relation and field.auto_created:
                    continue  # pomijamy reverse relations i pola automatyczne

                field_name = field.name
                verbose_name = (field.verbose_name.title() if hasattr(field, 'verbose_name') and field.verbose_name else field_name.replace('_', ' ').title())
                field_type = field.get_internal_type()
                can_be_null = field.null
                can_be_blank = field.blank
                max_length = field.max_length if hasattr(field, 'max_length') else ""
                choices = ""
                if field.choices:
                    choices = " | ".join([f"{k}: {v}" for k, v in field.choices])

                related_model = ""
                related_name = ""
                relation_type = ""

                if field.is_relation:
                    if field.related_model:
                        related_model = field.related_model.__name__
                    related_name = field.related_name or "(brak - używane domyślne)"
                    relation_type = RELATION_TYPES.get(type(field), "Inne")

                comments = field.help_text or ""

                rows.append([
                    app_label,
                    model_name,
                    verbose_plural,
                    field_name,
                    verbose_name,
                    field_type,
                    can_be_null,
                    can_be_blank,
                    max_length,
                    choices,
                    related_model,
                    related_name,
                    relation_type,
                    comments
                ])

        filename = options['output']
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"Zapisano do {filename} – {len(rows)-1} wierszy"))