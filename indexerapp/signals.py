from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import logging

from .models import Content, Layouts, Quires, Calendar, Decoration, ManuscriptHands, ManuscriptMusicNotations, Watermarks

# For downscaling images, we use the utility function from utils/image_processing.py
from .utils.image_processing import downscale_if_raster


logger = logging.getLogger(__name__)

# Signal for Layouts, Quires, Calendar, Decoration, ManuscriptHands, and ManuscriptMusicNotations
@receiver(pre_save, sender=Layouts)
@receiver(pre_save, sender=Quires)
@receiver(pre_save, sender=Calendar)
@receiver(pre_save, sender=Decoration)
@receiver(pre_save, sender=ManuscriptHands)
@receiver(pre_save, sender=ManuscriptMusicNotations)
def auto_populate_digital_page_number(sender, instance, **kwargs):
    if instance.where_in_ms_from:
        contents = Content.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from,
            digital_page_number__isnull=False
        )
        if contents.exists():
            if contents.count() > 1:
                # Log the multiple records
                logger.warning(
                    f"Multiple Content records found for manuscript {instance.manuscript_id} "
                    f"and where_in_ms_from '{instance.where_in_ms_from}' with non-null digital_page_number. "
                    f"Record IDs: {list(contents.values_list('id', flat=True))}. "
                    "Choosing the first one."
                )
            # Choose the first one
            content = contents.first()
            instance.digital_page_number = content.digital_page_number
        else:
            instance.digital_page_number = None

# Signal for Content to update related models
@receiver(post_save, sender=Content)
def update_related_models_digital_page_number(sender, instance, **kwargs):
    """
    Update digital_page_number in related models when Content is saved.
    """
    if instance.where_in_ms_from and instance.digital_page_number is not None:
        # Update Layouts
        Layouts.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from
        ).update(digital_page_number=instance.digital_page_number)

        # Update Quires
        Quires.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from
        ).update(digital_page_number=instance.digital_page_number)

        # Update Calendar
        Calendar.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from
        ).update(digital_page_number=instance.digital_page_number)

        # Update Decoration
        Decoration.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from
        ).update(digital_page_number=instance.digital_page_number)

        # Update ManuscriptHands
        ManuscriptHands.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from
        ).update(digital_page_number=instance.digital_page_number)

        # Update ManuscriptMusicNotations
        ManuscriptMusicNotations.objects.filter(
            manuscript=instance.manuscript,
            where_in_ms_from=instance.where_in_ms_from
        ).update(digital_page_number=instance.digital_page_number)


@receiver(pre_save, sender=Layouts)
@receiver(pre_save, sender=Quires)
@receiver(pre_save, sender=Watermarks)
def auto_downscale_image(sender, instance, **kwargs):
    # Only process if the image field has changed
    if not instance.pk:
        return  # New object → we'll handle after first save if needed

    field_name = 'graph_img' if sender in (Layouts, Quires) else 'watermark_img'
    old_instance = sender.objects.get(pk=instance.pk)
    old_file = getattr(old_instance, field_name)
    new_file = getattr(instance, field_name)

    # If file didn't change → skip
    if old_file == new_file or not new_file:
        return

    max_size = 500 if sender == Watermarks else 300
    downscale_if_raster(new_file, max_long_edge=max_size)