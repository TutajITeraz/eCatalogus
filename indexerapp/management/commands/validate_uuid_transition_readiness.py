from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from etlapp.model_categories import SYNC_CATEGORIES, get_model_category, get_sync_model_names
from etlapp.uuid_fk import resolve_shadow_uuid


def _iter_selected_models(model_names=None, categories=None):
    selected_model_names = model_names or get_sync_model_names()
    valid_models = set(get_sync_model_names())
    invalid_models = sorted(set(selected_model_names) - valid_models)
    if invalid_models:
        raise ValueError(f'Unknown or non-sync models: {", ".join(invalid_models)}')

    selected_categories = set(categories or [])
    invalid_categories = sorted(selected_categories - SYNC_CATEGORIES)
    if invalid_categories:
        raise ValueError(f'Unknown ETL categories: {", ".join(invalid_categories)}')

    for model_name in selected_model_names:
        model = apps.get_model('indexerapp', model_name)
        category = get_model_category(model.__name__)
        if selected_categories and category not in selected_categories:
            continue
        yield model, category


class Command(BaseCommand):
    help = 'Runs a detailed readiness validation for UUID FK transition, including self-FK, required FK, shadow UUID, and M2M UUID checks.'

    def add_arguments(self, parser):
        parser.add_argument('--model', action='append', dest='models', help='Specific indexerapp model name to process. Can be passed multiple times.')
        parser.add_argument('--category', action='append', dest='categories', help='Limit processing to ETL categories: main, shared, ms.')
        parser.add_argument('--chunk-size', type=int, default=200, help='Iterator chunk size for queryset traversal.')
        parser.add_argument('--fail-on-issues', action='store_true', help='Exit with a command error if readiness issues are found.')

    def handle(self, *args, **options):
        issues_found = False

        try:
            selected_models = list(_iter_selected_models(options['models'], options['categories']))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        summary = {
            'models': 0,
            'self_fk_fields': 0,
            'required_fk_fields': 0,
            'm2m_fields': 0,
            'issues': 0,
        }

        for model, category in selected_models:
            summary['models'] += 1
            queryset = model.objects.all().order_by('pk')

            fk_specs = []
            m2m_fields = []
            for field in model._meta.concrete_fields:
                if not isinstance(field, models.ForeignKey):
                    continue
                related_model = field.related_model
                if related_model is None or related_model._meta.app_label != 'indexerapp':
                    continue
                if get_model_category(related_model.__name__) not in SYNC_CATEGORIES:
                    continue

                shadow_field = None
                try:
                    shadow_field = model._meta.get_field(f'{field.name}_uuid')
                except FieldDoesNotExist:
                    shadow_field = None

                fk_specs.append((field, shadow_field))
                if related_model == model:
                    summary['self_fk_fields'] += 1
                if not field.null:
                    summary['required_fk_fields'] += 1

            for field in model._meta.many_to_many:
                related_model = field.related_model
                if related_model is None or related_model._meta.app_label != 'indexerapp':
                    continue
                if get_model_category(related_model.__name__) not in SYNC_CATEGORIES:
                    continue
                m2m_fields.append(field)
                summary['m2m_fields'] += 1

            if fk_specs:
                queryset = queryset.select_related(*[field.name for field, _ in fk_specs])
            if m2m_fields:
                queryset = queryset.prefetch_related(*[field.name for field in m2m_fields])

            field_counters = {
                field.name: {
                    'owner_missing_uuid': 0,
                    'related_missing_uuid': 0,
                    'missing_shadow': 0,
                    'mismatch': 0,
                    'stale_without_fk': 0,
                    'self_reference': 0,
                    'missing_shadow_field': 0,
                }
                for field, _shadow_field in fk_specs
            }
            m2m_counters = {
                field.name: {
                    'relations_checked': 0,
                    'owner_missing_uuid': 0,
                    'related_missing_uuid': 0,
                    'custom_through': 0 if field.remote_field.through._meta.auto_created else 1,
                }
                for field in m2m_fields
            }

            for instance in queryset.iterator(chunk_size=options['chunk_size']):
                owner_uuid = getattr(instance, 'uuid', None)
                for field, shadow_field in fk_specs:
                    counters = field_counters[field.name]
                    related_pk = getattr(instance, field.attname)
                    if related_pk is None:
                        if shadow_field is not None and getattr(instance, shadow_field.attname) is not None:
                            counters['stale_without_fk'] += 1
                        continue

                    if owner_uuid is None:
                        counters['owner_missing_uuid'] += 1

                    related_object = getattr(instance, field.name, None)
                    if related_object == instance:
                        counters['self_reference'] += 1

                    expected_uuid = resolve_shadow_uuid(instance, field)
                    if expected_uuid is None:
                        counters['related_missing_uuid'] += 1

                    if shadow_field is None:
                        counters['missing_shadow_field'] += 1
                        continue

                    current_shadow_uuid = getattr(instance, shadow_field.attname)
                    if current_shadow_uuid is None:
                        counters['missing_shadow'] += 1
                        continue

                    if expected_uuid is not None and current_shadow_uuid != expected_uuid:
                        counters['mismatch'] += 1

                for field in m2m_fields:
                    counters = m2m_counters[field.name]
                    related_objects = list(getattr(instance, field.name).all())
                    if not related_objects:
                        continue

                    counters['relations_checked'] += len(related_objects)
                    if owner_uuid is None:
                        counters['owner_missing_uuid'] += 1
                    counters['related_missing_uuid'] += sum(1 for related_object in related_objects if getattr(related_object, 'uuid', None) is None)

            for field, shadow_field in fk_specs:
                counters = field_counters[field.name]
                total_issues = sum(counters.values()) - counters['self_reference']
                status = 'ISSUES' if total_issues else 'OK'
                issues_found = issues_found or bool(total_issues)
                summary['issues'] += total_issues
                shadow_name = shadow_field.attname if shadow_field is not None else 'missing'
                self.stdout.write(
                    f'FK {model.__name__}.{field.name} [{category}] shadow={shadow_name} status={status} '
                    f'owner_missing_uuid={counters["owner_missing_uuid"]} '
                    f'related_missing_uuid={counters["related_missing_uuid"]} '
                    f'missing_shadow={counters["missing_shadow"]} '
                    f'mismatch={counters["mismatch"]} '
                    f'stale_without_fk={counters["stale_without_fk"]} '
                    f'self_reference={counters["self_reference"]} '
                    f'missing_shadow_field={counters["missing_shadow_field"]} '
                    f'required={"yes" if not field.null else "no"}'
                )

            for field in m2m_fields:
                counters = m2m_counters[field.name]
                total_issues = counters['owner_missing_uuid'] + counters['related_missing_uuid'] + counters['custom_through']
                status = 'ISSUES' if total_issues else 'OK'
                issues_found = issues_found or bool(total_issues)
                summary['issues'] += total_issues
                self.stdout.write(
                    f'M2M {model.__name__}.{field.name} [{category}] status={status} '
                    f'relations_checked={counters["relations_checked"]} '
                    f'owner_missing_uuid={counters["owner_missing_uuid"]} '
                    f'related_missing_uuid={counters["related_missing_uuid"]} '
                    f'custom_through={counters["custom_through"]}'
                )

        self.stdout.write(
            'SUMMARY '
            f'models={summary["models"]} '
            f'self_fk_fields={summary["self_fk_fields"]} '
            f'required_fk_fields={summary["required_fk_fields"]} '
            f'm2m_fields={summary["m2m_fields"]} '
            f'issues={summary["issues"]}'
        )

        if issues_found and options['fail_on_issues']:
            raise CommandError('UUID transition readiness validation failed.')

        if issues_found:
            self.stdout.write(self.style.WARNING('UUID transition readiness validation completed with issues.'))
            return

        self.stdout.write(self.style.SUCCESS('UUID transition readiness validation passed for all selected models.'))