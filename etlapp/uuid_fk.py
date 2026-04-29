from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from .model_categories import SYNC_CATEGORIES, get_model_category, get_sync_model_names


def get_uuid_shadow_model_names(categories=None):
    if not categories:
        return get_sync_model_names()

    invalid_categories = sorted(set(categories) - SYNC_CATEGORIES)
    if invalid_categories:
        raise ValueError(f'Unknown ETL categories: {", ".join(invalid_categories)}')

    return [
        model_name
        for model_name in get_sync_model_names()
        if get_model_category(model_name) in categories
    ]


def get_model_uuid_shadow_fk_specs(model):
    specs = []

    for field in model._meta.concrete_fields:
        if not isinstance(field, models.ForeignKey):
            continue

        related_model = field.related_model
        if related_model is None or related_model._meta.app_label != 'indexerapp':
            continue

        if get_model_category(model.__name__) not in SYNC_CATEGORIES:
            continue
        if get_model_category(related_model.__name__) not in SYNC_CATEGORIES:
            continue

        shadow_field_name = f'{field.name}_uuid'
        try:
            shadow_field = model._meta.get_field(shadow_field_name)
        except FieldDoesNotExist:
            continue

        specs.append((field, shadow_field))

    return tuple(specs)


def iter_models_with_uuid_shadow_fks(model_names=None, categories=None):
    selected_model_names = model_names or get_uuid_shadow_model_names(categories)

    valid_models = set(get_sync_model_names())
    invalid_models = sorted(set(selected_model_names) - valid_models)
    if invalid_models:
        raise ValueError(f'Unknown or non-sync models: {", ".join(invalid_models)}')

    for model_name in selected_model_names:
        model = apps.get_model('indexerapp', model_name)
        specs = get_model_uuid_shadow_fk_specs(model)
        if specs:
            yield model, specs


def resolve_shadow_uuid(instance, field):
    related_pk = getattr(instance, field.attname)
    if related_pk is None:
        return None

    related_object = getattr(instance, field.name, None)
    if related_object is not None and getattr(related_object, 'pk', None) == related_pk:
        return getattr(related_object, 'uuid', None)

    return field.related_model.objects.filter(pk=related_pk).values_list('uuid', flat=True).first()