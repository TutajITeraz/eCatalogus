from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from indexerapp.models import UUID_RELATION_COMPAT_ALIASES

from .model_categories import SYNC_CATEGORIES, get_model_category, get_sync_model_names


def get_legacy_fk_aliases(model):
    aliases = UUID_RELATION_COMPAT_ALIASES.get(model, {})
    return {canonical_name: legacy_name for legacy_name, canonical_name in aliases.items()}


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
    legacy_names_by_field = get_legacy_fk_aliases(model)

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

        legacy_name = legacy_names_by_field.get(field.name)
        if legacy_name is None and field.name.endswith('_uuid'):
            legacy_name = field.name[:-5]

        if legacy_name is None:
            continue

        specs.append((legacy_name, field))

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

    try:
        related_object = getattr(instance, field.name, None)
    except field.related_model.DoesNotExist:
        related_object = None

    target_attname = field.target_field.attname
    if related_object is not None and getattr(related_object, target_attname, None) == related_pk:
        return getattr(related_object, 'uuid', None)

    return field.related_model.objects.filter(**{target_attname: related_pk}).values_list('uuid', flat=True).first()