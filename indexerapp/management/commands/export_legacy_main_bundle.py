import json

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from etlapp.model_categories import get_model_category, get_sync_model_names
from etlapp.services import _serialize_value
from etlapp.uuid_utils import build_deterministic_sync_uuid


def _resolve_instance_uuid(instance):
    instance_uuid = getattr(instance, 'uuid', None)
    if instance_uuid:
        return instance_uuid
    return build_deterministic_sync_uuid(instance._meta.label, instance.pk)


def _serialize_legacy_instance(instance):
    payload = {
        'source_pk': instance.pk,
        'uuid': str(_resolve_instance_uuid(instance)),
    }
    relation_shadow_field_names = {
        f'{field.name}_uuid'
        for field in instance._meta.concrete_fields
        if field.is_relation and field.many_to_one
    }

    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name == 'uuid':
            continue
        if field.name in relation_shadow_field_names:
            continue

        value = getattr(instance, field.attname)

        if field.is_relation and field.many_to_one:
            payload[field.name] = _serialize_value(value)
            try:
                related_object = getattr(instance, field.name)
            except ObjectDoesNotExist:
                related_object = None
            payload[f'{field.name}_uuid'] = (
                str(_resolve_instance_uuid(related_object)) if related_object is not None else None
            )
            continue

        payload[field.name] = _serialize_value(value)

    for field in instance._meta.many_to_many:
        related_objects = list(getattr(instance, field.name).all())
        payload[field.name] = [related_object.pk for related_object in related_objects]
        payload[f'{field.name}_uuids'] = [
            str(_resolve_instance_uuid(related_object))
            for related_object in related_objects
        ]

    return payload


def _get_legacy_models_in_dependency_order(category, *, limit_to_model_names=None):
    ordered_models = []
    category_model_names = [
        model_name
        for model_name in get_sync_model_names()
        if get_model_category(model_name) == category
    ]
    if limit_to_model_names is not None:
        allowed = set(limit_to_model_names)
        category_model_names = [model_name for model_name in category_model_names if model_name in allowed]
    remaining = {
        model_name: _get_same_category_dependencies(apps.get_model('indexerapp', model_name), category)
        for model_name in category_model_names
    }
    resolved = set()

    while remaining:
        ready = sorted(
            model_name
            for model_name, dependencies in remaining.items()
            if dependencies.issubset(resolved)
        )
        if not ready:
            ready = sorted(remaining)

        for model_name in ready:
            ordered_models.append(apps.get_model('indexerapp', model_name))
            resolved.add(model_name)
            remaining.pop(model_name)

    return ordered_models


def _get_same_category_dependencies(model, category):
    dependencies = set()

    for field in model._meta.concrete_fields:
        if not field.is_relation or not field.many_to_one:
            continue

        related_model = field.related_model
        if related_model is None or related_model._meta.app_label != 'indexerapp':
            continue
        if related_model.__name__ == model.__name__:
            continue
        if get_model_category(related_model.__name__) != category:
            continue

        dependencies.add(related_model.__name__)

    for field in model._meta.many_to_many:
        related_model = field.related_model
        if related_model is None or related_model._meta.app_label != 'indexerapp':
            continue
        if related_model.__name__ == model.__name__:
            continue
        if get_model_category(related_model.__name__) != category:
            continue

        dependencies.add(related_model.__name__)

    return dependencies


def _get_shared_dependency_model_names_for_main():
    dependency_model_names = set()
    for model in _get_legacy_models_in_dependency_order('main'):
        for field in model._meta.concrete_fields:
            if not field.is_relation or not field.many_to_one:
                continue
            related_model = field.related_model
            if related_model is None or related_model._meta.app_label != 'indexerapp':
                continue
            if get_model_category(related_model.__name__) != 'shared':
                continue
            dependency_model_names.add(related_model.__name__)

        for field in model._meta.many_to_many:
            related_model = field.related_model
            if related_model is None or related_model._meta.app_label != 'indexerapp':
                continue
            if get_model_category(related_model.__name__) != 'shared':
                continue
            dependency_model_names.add(related_model.__name__)

    return dependency_model_names


def _build_model_payloads(models, category):
    exported_models = []
    total_records = 0

    for model in models:
        records = list(model.objects.all().order_by('pk'))
        if not records:
            continue

        serialized = [_serialize_legacy_instance(record) for record in records]
        total_records += len(serialized)
        exported_models.append(
            {
                'model': model._meta.label,
                'category': category,
                'count': len(serialized),
                'results': serialized,
            }
        )

    return exported_models, total_records


class Command(BaseCommand):
    help = 'Exports legacy main dictionaries to a deterministic ETL-compatible JSON bundle.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            required=True,
            help='Output JSON file path.',
        )

    def handle(self, *args, **options):
        output_path = options['output']
        shared_dependency_payloads, shared_dependency_record_count = _build_model_payloads(
            _get_legacy_models_in_dependency_order(
                'shared',
                limit_to_model_names=_get_shared_dependency_model_names_for_main(),
            ),
            'shared',
        )
        exported_models, total_records = _build_model_payloads(
            _get_legacy_models_in_dependency_order('main'),
            'main',
        )

        payload = {
            'site_name': 'legacy-main-bootstrap',
            'category': 'main',
            'legacy_source': True,
            'uuid_strategy': 'deterministic:model_label+pk',
            'model_count': len(exported_models),
            'record_count': total_records,
            'shared_dependency_model_count': len(shared_dependency_payloads),
            'shared_dependency_record_count': shared_dependency_record_count,
            'shared_dependencies': shared_dependency_payloads,
            'models': exported_models,
        }

        with open(output_path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write('\n')

        self.stdout.write(
            self.style.SUCCESS(
                f'Exported legacy main bundle model_count={payload["model_count"]} '
                f'record_count={payload["record_count"]} to {output_path}'
            )
        )