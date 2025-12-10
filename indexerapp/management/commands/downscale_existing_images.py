# management/commands/downscale_existing_images.py
from django.core.management.base import BaseCommand
from django.db.models import Q

from indexerapp.models import Layouts, Quires, Watermarks
from indexerapp.utils.image_processing import downscale_if_raster


class Command(BaseCommand):
    help = "Downscale all existing raster images in Layouts, Quires, and Watermarks if they exceed limits"

    def handle(self, *args, **options):
        total_resized = 0

        # Layouts & Quires → max 300px
        for model, field_name in [(Layouts, 'graph_img'), (Quires, 'graph_img')]:
            instances = model.objects.exclude(**{f"{field_name}__isnull": True}).exclude(**{f"{field_name}": ''})
            self.stdout.write(f"Processing {model.__name__} ({instances.count()} images)...")

            for obj in instances:
                image_field = getattr(obj, field_name)
                if image_field and downscale_if_raster(image_field, max_long_edge=300):
                    total_resized += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Resized {model.__name__} #{obj.pk} - {image_field.name}")
                    )

        # Watermarks → max 500px
        watermarks = Watermarks.objects.exclude(watermark_img__isnull=True).exclude(watermark_img='')
        self.stdout.write(f"Processing Watermarks ({watermarks.count()} images)...")
        for wm in watermarks:
            if wm.watermark_img and downscale_if_raster(wm.watermark_img, max_long_edge=500):
                total_resized += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Resized Watermark #{wm.pk} - {wm.watermark_img.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Done! Total images resized: {total_resized}")
        )