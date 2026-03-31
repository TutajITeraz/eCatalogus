from django.apps import apps
from django.db.models.signals import pre_delete, pre_save, post_save
from django.dispatch import receiver
import logging
import uuid

from etlapp.model_categories import get_model_category, get_sync_model_names

from .models import Bibliography, Content, Contributors, DeletedRecord, Hands, Layouts, Quires, Calendar, Decoration, ManuscriptHands, ManuscriptMusicNotations, Watermarks

# For downscaling images, we use the utility function from utils/image_processing.py
from .utils.image_processing import downscale_if_raster


logger = logging.getLogger(__name__)

SHARED_SYNC_SENDERS = (Bibliography, Contributors, Hands, Watermarks)


def _ensure_sync_uuid(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if getattr(instance, 'uuid', None) is None:
        instance.uuid = uuid.uuid4()


def _has_shared_model_changes(sender, instance):
    if not instance.pk:
        return False

    current_instance = sender.objects.filter(pk=instance.pk).first()
    if current_instance is None:
        return False

    ignored_fields = {'version', 'entry_date'}
    for field in sender._meta.concrete_fields:
        if field.name in ignored_fields:
            continue
        if getattr(current_instance, field.attname) != getattr(instance, field.attname):
            return True

    return False


def _record_deleted_sync_instance(sender, instance, **kwargs):
    object_uuid = getattr(instance, 'uuid', None)
    category = get_model_category(sender.__name__)
    if not object_uuid or category == 'unassigned':
        return

    DeletedRecord.objects.update_or_create(
        model_label=sender._meta.label,
        object_uuid=object_uuid,
        defaults={
            'category': category,
            'source_pk': str(instance.pk) if instance.pk is not None else None,
        },
    )


for model_name in get_sync_model_names():
    pre_save.connect(
        _ensure_sync_uuid,
        sender=apps.get_model('indexerapp', model_name),
        weak=False,
        dispatch_uid=f'etl_assign_uuid_{model_name}',
    )
    pre_delete.connect(
        _record_deleted_sync_instance,
        sender=apps.get_model('indexerapp', model_name),
        weak=False,
        dispatch_uid=f'etl_deleted_record_{model_name}',
    )

# Signal for Layouts, Quires, Calendar, Decoration, ManuscriptHands, and ManuscriptMusicNotations
@receiver(pre_save, sender=Layouts)
@receiver(pre_save, sender=Quires)
@receiver(pre_save, sender=Calendar)
@receiver(pre_save, sender=Decoration)
@receiver(pre_save, sender=ManuscriptHands)
@receiver(pre_save, sender=ManuscriptMusicNotations)
def auto_populate_digital_page_number(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
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
    if kwargs.get('raw'):
        return
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
    if kwargs.get('raw'):
        return
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


@receiver(pre_save, sender=Bibliography)
@receiver(pre_save, sender=Contributors)
@receiver(pre_save, sender=Hands)
@receiver(pre_save, sender=Watermarks)
def increment_shared_sync_version(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if sender not in SHARED_SYNC_SENDERS:
        return

    if not instance.pk:
        if instance.version is None:
            instance.version = 1
        return

    current_instance = sender.objects.filter(pk=instance.pk).first()
    if current_instance is None:
        if instance.version is None:
            instance.version = 1
        return

    if _has_shared_model_changes(sender, instance):
        instance.version = (current_instance.version or 0) + 1
    else:
        instance.version = current_instance.version