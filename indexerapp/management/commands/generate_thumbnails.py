# yourapp/management/commands/generate_missing_thumbnails.py

from django.core.management.base import BaseCommand
from indexerapp.models import Manuscripts  # Replace with correct import path


class Command(BaseCommand):
    help = "Generate missing thumbnails (300px max side) for all manuscripts with images"

    def handle(self, *args, **options):
        # Find manuscripts that have an image but no thumbnail
        queryset = Manuscripts.objects.filter(
            image__isnull=False
        ).exclude(
            thumbnail__isnull=False
        ).exclude(
            thumbnail__exact=''
        )

        total = queryset.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("All manuscripts already have thumbnails!"))
            return

        self.stdout.write(f"Generating thumbnails for {total} manuscripts...")

        for i, manuscript in enumerate(queryset.iterator(), start=1):
            manuscript.generate_thumbnail(save=True)
            if i % 50 == 0:
                self.stdout.write(f"  Processed {i}/{total}...")

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Generated {total} thumbnails.")
        )