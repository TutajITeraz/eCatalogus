import base64
from decimal import Decimal
import json
import os
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from indexerapp.models import DeletedRecord, Manuscripts

from .model_categories import SYNC_CATEGORIES, get_model_category, get_sync_model_names, summarize_categories


ETL_IMPORT_PERMISSION_NAMES = [
    'add_manuscripts',
    'add_content',
    'add_bibliography',
    'add_editioncontent',
    'add_formulas',
    'add_ritenames',
    'add_timereference',
]


class ETLImportConflictError(Exception):
    def __init__(self, message, conflict=None, extra_payload=None):
        super().__init__(message)
        self.conflict = conflict
        self.extra_payload = extra_payload or {}

    def to_payload(self):
        payload = {'detail': str(self)}
        if self.conflict is not None:
            payload['conflict'] = self.conflict
        payload.update(self.extra_payload)
        return payload


def build_status_payload():
    slave_urls = list(getattr(settings, 'ETL_SLAVE_URLS', []))
    role = getattr(settings, 'ETL_ROLE', 'undefined')
    model_names = [
        model.__name__
        for model in apps.get_app_config('indexerapp').get_models()
    ]

    return {
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'role': role,
        'master_url': getattr(settings, 'ETL_MASTER_URL', None),
        'slave_urls': slave_urls,
        'has_api_token': bool(getattr(settings, 'ETL_API_TOKEN', '')),
        'model_category_counts': dict(summarize_categories(model_names)),
    }


def get_etl_peer_configs():
    peers = []
    seen_urls = set()
    peer_tokens = getattr(settings, 'ETL_PEER_TOKENS', {}) or {}

    master_url = _normalize_peer_url(getattr(settings, 'ETL_MASTER_URL', None))
    if master_url:
        peers.append({
            'id': 'master',
            'label': 'Master',
            'url': master_url,
            'api_token': peer_tokens.get(master_url) or getattr(settings, 'ETL_API_TOKEN', ''),
        })
        seen_urls.add(master_url)

    for index, slave_url in enumerate(getattr(settings, 'ETL_SLAVE_URLS', []), start=1):
        normalized_url = _normalize_peer_url(slave_url)
        if not normalized_url or normalized_url in seen_urls:
            continue
        peers.append({
            'id': f'slave-{index}',
            'label': f'Slave {index}',
            'url': normalized_url,
            'api_token': peer_tokens.get(normalized_url) or getattr(settings, 'ETL_API_TOKEN', ''),
        })
        seen_urls.add(normalized_url)

    return peers


def resolve_etl_peer(peer_id):
    for peer in get_etl_peer_configs():
        if peer['id'] == peer_id:
            return peer
    raise ValueError(f'Unknown ETL peer: {peer_id}')


def user_can_manage_etl(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    required_permissions = [f'indexerapp.{permission}' for permission in ETL_IMPORT_PERMISSION_NAMES]
    return user.has_perms(required_permissions)


def fetch_remote_etl_json(peer_url, path, query=None, method='GET', payload=None, timeout=60, api_token=None):
    url = _build_peer_url(peer_url, path, query)
    headers = {'Accept': 'application/json'}

    api_token = api_token if api_token is not None else getattr(settings, 'ETL_API_TOKEN', '')
    if api_token:
        headers['Authorization'] = f'Token {api_token}'

    request_body = None
    if payload is not None:
        request_body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    request = urllib_request.Request(url, data=request_body, headers=headers, method=method)

    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8')
    except urllib_error.HTTPError as exc:
        detail = _extract_remote_error(exc)
        raise ValueError(f'Remote ETL request failed for {url} ({exc.code}): {detail}') from exc
    except urllib_error.URLError as exc:
        raise ValueError(f'Cannot reach ETL peer {peer_url}: {exc.reason}') from exc

    if not body:
        return {}

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f'Remote ETL response from {url} is not valid JSON.') from exc


def build_deleted_records_payload(category, since=None):
    if category not in SYNC_CATEGORIES:
        raise ValueError(f'Unsupported ETL category: {category}')

    queryset = DeletedRecord.objects.filter(category=category)
    if since is not None:
        if timezone.is_naive(since):
            since = timezone.make_aware(since, timezone.get_current_timezone())
        queryset = queryset.filter(deleted_at__gt=since)

    records = list(
        queryset.order_by('deleted_at', 'model_label', 'object_uuid').values(
            'model_label',
            'category',
            'object_uuid',
            'source_pk',
            'deleted_at',
        )
    )

    return {
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'category': category,
        'since': since.isoformat() if since is not None else None,
        'count': len(records),
        'results': [
            {
                **record,
                'object_uuid': str(record['object_uuid']),
                'deleted_at': record['deleted_at'].isoformat(),
            }
            for record in records
        ],
    }


@transaction.atomic
def apply_deleted_records_payload(category, payload):
    if category not in SYNC_CATEGORIES:
        raise ValueError(f'Unsupported ETL category: {category}')

    if not isinstance(payload, dict):
        raise ValueError('Deleted records payload must be an object.')

    payload_category = payload.get('category')
    if payload_category and payload_category != category:
        raise ValueError(f'Deleted records payload category mismatch: expected {category}, got {payload_category}.')

    results = payload.get('results', [])
    if not isinstance(results, list):
        raise ValueError('Deleted records payload must include a results list.')

    summary = {
        'category': category,
        'requested': len(results),
        'deleted': 0,
        'missing': 0,
        'skipped': 0,
    }

    for record in results:
        if not isinstance(record, dict):
            raise ValueError('Each deleted record entry must be an object.')

        model_label = record.get('model_label')
        object_uuid = record.get('object_uuid')
        if not model_label or not object_uuid:
            summary['skipped'] += 1
            continue

        model = apps.get_model(model_label)
        if model is None or model._meta.app_label != 'indexerapp':
            summary['skipped'] += 1
            continue

        instance = model.objects.filter(uuid=object_uuid).first()
        if instance is None:
            summary['missing'] += 1
            continue

        instance.delete()
        summary['deleted'] += 1

    return summary


def build_delta_export_payload(category, since=None):
    if category not in {'main', 'shared'}:
        raise ValueError(f'Unsupported delta export category: {category}')

    if since is not None and timezone.is_naive(since):
        since = timezone.make_aware(since, timezone.get_current_timezone())

    exported_models = []
    total_records = 0

    for model_name in get_sync_model_names():
        if get_model_category(model_name) != category:
            continue

        model = apps.get_model('indexerapp', model_name)
        entry_date_field = _get_concrete_field(model, 'entry_date')
        if entry_date_field is None:
            continue

        concrete_fk_fields = [
            field for field in model._meta.concrete_fields
            if field.is_relation and field.many_to_one
        ]
        m2m_fields = list(model._meta.many_to_many)

        queryset = model.objects.all().order_by('entry_date', 'pk')
        if since is not None:
            queryset = queryset.filter(entry_date__gt=since)
        if concrete_fk_fields:
            queryset = queryset.select_related(*[field.name for field in concrete_fk_fields])
        if m2m_fields:
            queryset = queryset.prefetch_related(*[field.name for field in m2m_fields])

        results = [_serialize_instance(instance) for instance in queryset]
        if not results:
            continue

        total_records += len(results)
        exported_models.append({
            'model': model._meta.label,
            'category': category,
            'count': len(results),
            'results': results,
        })

    return {
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'category': category,
        'since': since.isoformat() if since is not None else None,
        'model_count': len(exported_models),
        'record_count': total_records,
        'models': exported_models,
    }


def build_manuscript_list_payload():
    manuscripts = Manuscripts.objects.order_by('entry_date', 'pk')

    return {
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'count': manuscripts.count(),
        'results': [
            {
                'uuid': str(manuscript.uuid) if manuscript.uuid else None,
                'name': manuscript.name,
                'rism_id': manuscript.rism_id,
                'sync_status': manuscript.sync_status,
                'entry_date': manuscript.entry_date.isoformat() if manuscript.entry_date else None,
            }
            for manuscript in manuscripts
        ],
    }


def build_manuscript_export_payload(manuscript_uuid):
    manuscript = Manuscripts.objects.filter(uuid=manuscript_uuid).first()
    if manuscript is None:
        raise ValueError(f'Unknown manuscript uuid: {manuscript_uuid}')

    ordered_models = _get_category_models_in_dependency_order('ms')
    included_pks = {'Manuscripts': {manuscript.pk}}
    exported_models = []
    total_records = 0
    media_files = []
    seen_media_paths = set()

    for model in ordered_models:
        if model is Manuscripts:
            records = [manuscript]
        else:
            queryset = _build_manuscript_model_queryset(model, included_pks)
            if queryset is None:
                continue
            records = list(queryset.order_by('entry_date', 'pk'))

        if not records:
            continue

        included_pks[model.__name__] = {record.pk for record in records}
        _collect_media_files_for_records(model, records, media_files, seen_media_paths)
        serialized = [_serialize_instance(record) for record in records]
        total_records += len(serialized)
        exported_models.append({
            'model': model._meta.label,
            'category': 'ms',
            'count': len(serialized),
            'results': serialized,
        })

    return {
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'category': 'ms',
        'manuscript_uuid': str(manuscript.uuid),
        'manuscript_name': manuscript.name,
        'model_count': len(exported_models),
        'record_count': total_records,
        'models': exported_models,
        'media_files': media_files,
    }


def pull_remote_category(peer_url, category, since=None, force_remote_uuids=None, keep_local_uuids=None):
    if category not in {'main', 'shared'}:
        raise ValueError(f'Unsupported delta import category: {category}')

    query = {}
    if since:
        query['since'] = since

    export_payload = fetch_remote_etl_json(
        peer_url,
        f'/api/etl/{category}/export/',
        query=query or None,
        api_token=_get_peer_api_token(peer_url),
    )
    deleted_payload = fetch_remote_etl_json(
        peer_url,
        f'/api/etl/{category}/deleted/',
        query=query or None,
        api_token=_get_peer_api_token(peer_url),
    )

    with transaction.atomic():
        import_summary = import_delta_payload(
            category,
            export_payload,
            force_remote_uuids=force_remote_uuids,
            keep_local_uuids=keep_local_uuids,
        )
        delete_summary = apply_deleted_records_payload(category, deleted_payload)

    return {
        'peer_url': _normalize_peer_url(peer_url),
        'category': category,
        'since': since,
        'import_summary': import_summary,
        'delete_summary': delete_summary,
    }


def pull_remote_manuscript(peer_url, manuscript_uuid):
    manuscript_payload = fetch_remote_etl_json(
        peer_url,
        f'/api/etl/manuscripts/export/{manuscript_uuid}/',
        api_token=_get_peer_api_token(peer_url),
    )

    with transaction.atomic():
        import_summary = import_manuscript_payload(manuscript_payload)

    return {
        'peer_url': _normalize_peer_url(peer_url),
        'manuscript_uuid': str(manuscript_uuid),
        'import_summary': import_summary,
    }


@transaction.atomic
def import_delta_payload(category, payload, force_remote_uuids=None, keep_local_uuids=None):
    if category not in {'main', 'shared'}:
        raise ValueError(f'Unsupported delta import category: {category}')

    return _import_models_payload(
        category,
        payload,
        force_remote_uuids=force_remote_uuids,
        keep_local_uuids=keep_local_uuids,
    )


@transaction.atomic
def import_manuscript_payload(payload):
    summary = _import_models_payload('ms', payload)
    summary['media_summary'] = _import_media_files(payload.get('media_files', []))
    return summary


@transaction.atomic
def resolve_shared_conflict(
    peer_url,
    category,
    conflict_payload,
    resolution,
    since=None,
    force_remote_uuids=None,
    keep_local_uuids=None,
):
    if resolution == 'close':
        return {
            'resolution': 'close',
            'applied': False,
            'force_remote_uuids': sorted(_normalize_resolution_uuid_set(force_remote_uuids)),
            'keep_local_uuids': sorted(_normalize_resolution_uuid_set(keep_local_uuids)),
        }

    if resolution not in {'apply_remote', 'keep_local'}:
        raise ValueError(f'Unsupported conflict resolution: {resolution}')

    if category != 'shared':
        raise ValueError('Conflict resolution workflow currently supports only shared category pulls.')

    if not peer_url:
        raise ValueError('Conflict resolution requires a peer URL.')

    if not isinstance(conflict_payload, dict):
        raise ValueError('Conflict payload must be an object.')

    object_uuid = conflict_payload.get('object_uuid')
    if not object_uuid:
        raise ValueError('Conflict payload must include object_uuid.')

    force_remote_uuids = _normalize_resolution_uuid_set(force_remote_uuids)
    keep_local_uuids = _normalize_resolution_uuid_set(keep_local_uuids)

    if resolution == 'apply_remote':
        keep_local_uuids.discard(object_uuid)
        force_remote_uuids.add(object_uuid)
    elif resolution == 'keep_local':
        force_remote_uuids.discard(object_uuid)
        keep_local_uuids.add(object_uuid)

    try:
        pull_result = pull_remote_category(
            peer_url,
            category,
            since=since,
            force_remote_uuids=force_remote_uuids,
            keep_local_uuids=keep_local_uuids,
        )
    except ETLImportConflictError as exc:
        raise ETLImportConflictError(
            str(exc),
            conflict=exc.conflict,
            extra_payload={
                'force_remote_uuids': sorted(force_remote_uuids),
                'keep_local_uuids': sorted(keep_local_uuids),
            },
        ) from exc

    return {
        'resolution': resolution,
        'applied': resolution == 'apply_remote',
        'kept_local': resolution == 'keep_local',
        'pull_result': pull_result,
        'force_remote_uuids': sorted(force_remote_uuids),
        'keep_local_uuids': sorted(keep_local_uuids),
    }


def _import_models_payload(category, payload, force_remote_uuids=None, keep_local_uuids=None):
    if category not in {'main', 'shared', 'ms'}:
        raise ValueError(f'Unsupported delta import category: {category}')

    if not isinstance(payload, dict):
        raise ValueError('Request body must be an object.')

    model_payloads = payload.get('models')
    if not isinstance(model_payloads, list):
        raise ValueError('Request body must include a models list.')

    force_remote_uuids = set(force_remote_uuids or [])
    keep_local_uuids = set(keep_local_uuids or [])

    summary = {
        'category': category,
        'model_count': 0,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'models': [],
    }

    for model_payload in model_payloads:
        model_label = model_payload.get('model')
        if not model_label:
            raise ValueError('Each model payload must include model.')

        model = apps.get_model(model_label)
        if model is None or model._meta.app_label != 'indexerapp':
            raise ValueError(f'Unknown ETL model: {model_label}')

        model_name = model.__name__
        if get_model_category(model_name) != category:
            raise ValueError(f'Model {model_label} does not belong to category {category}.')

        records = model_payload.get('results', [])
        if not isinstance(records, list):
            raise ValueError(f'Model {model_label} results must be a list.')

        model_summary = _import_model_records(
            model,
            category,
            records,
            force_remote_uuids=force_remote_uuids,
            keep_local_uuids=keep_local_uuids,
        )
        summary['model_count'] += 1
        summary['created'] += model_summary['created']
        summary['updated'] += model_summary['updated']
        summary['skipped'] += model_summary['skipped']
        summary['models'].append(model_summary)

    return summary


def _import_model_records(model, category, records, force_remote_uuids=None, keep_local_uuids=None):
    model_summary = {
        'model': model._meta.label,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'count': len(records),
    }

    force_remote_uuids = set(force_remote_uuids or [])
    keep_local_uuids = set(keep_local_uuids or [])

    pending_records = list(records)
    last_error = None

    while pending_records:
        next_pending = []
        progress_made = False

        for record in pending_records:
            if not isinstance(record, dict):
                raise ValueError(f'Each record for {model._meta.label} must be an object.')

            record_uuid = record.get('uuid')
            if not record_uuid:
                raise ValueError(f'Record for {model._meta.label} is missing uuid.')

            try:
                attrs, m2m_values, self_referential_attnames = _prepare_import_values(model, record)
            except ValueError as exc:
                next_pending.append(record)
                last_error = exc
                continue

            existing = model.objects.filter(uuid=record_uuid).first()

            if category == 'shared' and existing is not None and record_uuid in keep_local_uuids:
                model_summary['skipped'] += 1
                progress_made = True
                continue

            if category == 'shared' and existing is not None:
                for attname in self_referential_attnames:
                    attrs[attname] = existing.pk
                _check_shared_conflict(
                    existing,
                    attrs,
                    m2m_values,
                    incoming_record=record,
                    force_remote=record_uuid in force_remote_uuids,
                )

            if existing is None:
                instance = model.objects.create(**_get_create_values(model, attrs))
                for attname in self_referential_attnames:
                    attrs[attname] = instance.pk
                if attrs:
                    model.objects.filter(pk=instance.pk).update(**attrs)
                instance.refresh_from_db()
                _apply_m2m_values(instance, m2m_values)
                model_summary['created'] += 1
                progress_made = True
                continue

            for attname in self_referential_attnames:
                attrs[attname] = existing.pk

            if _is_noop(existing, attrs, m2m_values):
                model_summary['skipped'] += 1
                progress_made = True
                continue

            if attrs:
                model.objects.filter(pk=existing.pk).update(**attrs)
            existing.refresh_from_db()
            _apply_m2m_values(existing, m2m_values)
            model_summary['updated'] += 1
            progress_made = True

        if not next_pending:
            break
        if not progress_made:
            raise last_error or ValueError(f'Unable to import records for {model._meta.label}.')

        pending_records = next_pending

    return model_summary


def _prepare_import_values(model, record):
    attrs = {}
    m2m_values = {}
    self_referential_attnames = []
    record_uuid = record.get('uuid')

    for field in model._meta.concrete_fields:
        if field.primary_key:
            continue

        if field.is_relation and field.many_to_one:
            uuid_key = f'{field.name}_uuid'
            if uuid_key in record and record[uuid_key] is not None:
                related_object = field.related_model.objects.filter(uuid=record[uuid_key]).first()
                if related_object is None:
                    if field.related_model == model and record[uuid_key] == record_uuid:
                        self_referential_attnames.append(field.attname)
                        continue
                    raise ValueError(
                        f'Missing related object for {model._meta.label}.{field.name} with uuid={record[uuid_key]}'
                    )
                attrs[field.attname] = related_object.pk
                continue

            if field.name in record:
                attrs[field.attname] = record[field.name]
            continue

        if field.name in record:
            attrs[field.name] = _coerce_field_value(field, record[field.name])

    for field in model._meta.many_to_many:
        uuid_key = f'{field.name}_uuids'
        if uuid_key in record:
            uuids = record[uuid_key] or []
            related_objects = list(field.related_model.objects.filter(uuid__in=uuids))
            found_by_uuid = {str(related_object.uuid): related_object for related_object in related_objects}
            missing = [uuid_value for uuid_value in uuids if uuid_value not in found_by_uuid]
            if missing:
                raise ValueError(
                    f'Missing related M2M objects for {model._meta.label}.{field.name}: {", ".join(missing)}'
                )
            m2m_values[field.name] = [found_by_uuid[uuid_value] for uuid_value in uuids]
            continue

        if field.name in record:
            ids = record[field.name] or []
            m2m_values[field.name] = list(field.related_model.objects.filter(pk__in=ids))

    return attrs, m2m_values, self_referential_attnames


def _coerce_field_value(field, value):
    if value is None:
        return None

    internal_type = field.get_internal_type()
    if internal_type == 'DateTimeField' and isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            parsed_date = parse_date(value)
            if parsed_date is not None:
                parsed = timezone.datetime.combine(parsed_date, timezone.datetime.min.time())
        if parsed is None:
            raise ValueError(f'Invalid datetime value for {field.name}: {value}')
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    if internal_type == 'DateField' and isinstance(value, str):
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(f'Invalid date value for {field.name}: {value}')
        return parsed

    return field.to_python(value)


def _get_create_values(model, attrs):
    create_values = {}
    for field in model._meta.concrete_fields:
        if field.primary_key:
            continue
        if field.attname in attrs:
            create_values[field.attname] = attrs[field.attname]
        elif field.name in attrs:
            create_values[field.name] = attrs[field.name]
    return create_values


def _apply_m2m_values(instance, m2m_values):
    for field_name, related_objects in m2m_values.items():
        getattr(instance, field_name).set(related_objects)


def _is_noop(instance, attrs, m2m_values):
    for key, expected_value in attrs.items():
        current_value = _get_comparable_instance_value(instance, key)
        if current_value != expected_value:
            return False

    for field_name, related_objects in m2m_values.items():
        current_ids = list(getattr(instance, field_name).order_by('pk').values_list('pk', flat=True))
        expected_ids = sorted(related_object.pk for related_object in related_objects)
        if current_ids != expected_ids:
            return False

    return True


def _get_comparable_instance_value(instance, key):
    field_name = key[:-3] if key.endswith('_id') else key
    try:
        field = instance._meta.get_field(field_name)
    except Exception:
        field = None

    current_value = getattr(instance, key)
    if field is not None and field.get_internal_type() in {'FileField', 'ImageField'}:
        return current_value.name if current_value else None

    return current_value


def _check_shared_conflict(existing, attrs, m2m_values, incoming_record=None, force_remote=False):
    if force_remote:
        return

    incoming_version = attrs.get('version')
    current_version = getattr(existing, 'version', None)

    if incoming_version is None:
        raise ETLImportConflictError(
            f'Shared import for {existing._meta.label} requires version.',
            conflict=_build_shared_conflict_payload(
                existing,
                incoming_record or {},
                reason='missing_version',
                incoming_version=incoming_version,
                current_version=current_version,
            ),
        )

    if current_version is None:
        return

    if incoming_version < current_version:
        raise ETLImportConflictError(
            f'Conflict for {existing._meta.label} uuid={existing.uuid}: incoming version {incoming_version} '
            f'is older than current version {current_version}.',
            conflict=_build_shared_conflict_payload(
                existing,
                incoming_record or {},
                reason='stale_version',
                incoming_version=incoming_version,
                current_version=current_version,
            ),
        )

    if incoming_version == current_version and not _is_noop(existing, attrs, m2m_values):
        raise ETLImportConflictError(
            f'Conflict for {existing._meta.label} uuid={existing.uuid}: incoming payload differs at version {incoming_version}.',
            conflict=_build_shared_conflict_payload(
                existing,
                incoming_record or {},
                reason='payload_diff',
                incoming_version=incoming_version,
                current_version=current_version,
            ),
        )


def _build_shared_conflict_payload(existing, incoming_record, reason, incoming_version, current_version):
    local_record = _serialize_instance(existing)
    differences = []

    for key in sorted(set(local_record.keys()) | set(incoming_record.keys())):
        local_value = _normalize_conflict_value(local_record.get(key))
        incoming_value = _normalize_conflict_value(incoming_record.get(key))
        if local_value == incoming_value:
            continue

        differences.append(
            {
                'field': key,
                'local': local_value,
                'incoming': incoming_value,
            }
        )

    return {
        'reason': reason,
        'model': existing._meta.label,
        'object_uuid': str(existing.uuid),
        'incoming_version': incoming_version,
        'current_version': current_version,
        'local_record': local_record,
        'incoming_record': incoming_record,
        'differences': differences,
    }


def _normalize_conflict_value(value):
    if isinstance(value, list):
        return sorted(_normalize_conflict_value(item) for item in value)
    if isinstance(value, dict):
        return {
            str(key): _normalize_conflict_value(item)
            for key, item in sorted(value.items())
        }
    return value


def _normalize_resolution_uuid_set(uuid_values):
    normalized = set()
    for uuid_value in uuid_values or []:
        if uuid_value is None:
            continue
        normalized.add(str(uuid_value))
    return normalized


def _get_category_models_in_dependency_order(category):
    ordered_models = []
    category_model_names = [
        model_name for model_name in get_sync_model_names()
        if get_model_category(model_name) == category
    ]
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

    return dependencies


def _build_manuscript_model_queryset(model, included_pks):
    manuscript_fk_names = [
        field.name
        for field in model._meta.concrete_fields
        if field.is_relation and field.many_to_one and getattr(field.related_model, '__name__', None) == 'Manuscripts'
    ]
    if manuscript_fk_names:
        query = Q()
        for field_name in manuscript_fk_names:
            query |= Q(**{f'{field_name}__in': included_pks['Manuscripts']})
        return model.objects.filter(query).distinct()

    dependency_queries = Q()
    found_dependency = False
    for field in model._meta.concrete_fields:
        if not field.is_relation or not field.many_to_one:
            continue

        related_model = field.related_model
        if related_model is None or related_model._meta.app_label != 'indexerapp':
            continue

        related_pks = included_pks.get(related_model.__name__)
        if not related_pks:
            continue

        dependency_queries |= Q(**{f'{field.name}__in': related_pks})
        found_dependency = True

    if not found_dependency:
        return None

    return model.objects.filter(dependency_queries).distinct()


def _serialize_instance(instance):
    payload = {}

    for field in instance._meta.concrete_fields:
        value = getattr(instance, field.attname)

        if field.is_relation and field.many_to_one:
            payload[field.name] = _serialize_value(value)
            related_object = getattr(instance, field.name)
            if related_object is not None and hasattr(related_object, 'uuid'):
                payload[f'{field.name}_uuid'] = _serialize_value(getattr(related_object, 'uuid', None))
            continue

        if field.get_internal_type() in {'FileField', 'ImageField'}:
            payload[field.name] = value.name if value else None
            continue

        payload[field.name] = _serialize_value(value)

    for field in instance._meta.many_to_many:
        related_objects = list(getattr(instance, field.name).all())
        payload[field.name] = [related_object.pk for related_object in related_objects]
        if related_objects and hasattr(related_objects[0], 'uuid'):
            payload[f'{field.name}_uuids'] = [
                _serialize_value(getattr(related_object, 'uuid', None))
                for related_object in related_objects
            ]
        else:
            payload[f'{field.name}_uuids'] = []

    return payload


def _collect_media_files_for_records(model, records, media_files, seen_media_paths):
    file_fields = [
        field for field in model._meta.concrete_fields
        if field.get_internal_type() in {'FileField', 'ImageField'}
    ]
    if not file_fields:
        return

    for record in records:
        for field in file_fields:
            field_file = getattr(record, field.name)
            file_name = getattr(field_file, 'name', None)
            if not file_name or file_name in seen_media_paths:
                continue
            if not field_file.storage.exists(file_name):
                continue

            with field_file.storage.open(file_name, 'rb') as handle:
                content = handle.read()

            media_files.append({
                'path': file_name,
                'content_base64': base64.b64encode(content).decode('ascii'),
            })
            seen_media_paths.add(file_name)


def _import_media_files(media_files):
    summary = {
        'count': 0,
        'created': 0,
        'updated': 0,
        'skipped': 0,
    }
    if not media_files:
        return summary
    if not isinstance(media_files, list):
        raise ValueError('media_files must be a list.')

    for media_file in media_files:
        if not isinstance(media_file, dict):
            raise ValueError('Each media file entry must be an object.')

        relative_path = _normalize_media_relative_path(media_file.get('path'))
        encoded_content = media_file.get('content_base64')
        if not relative_path or encoded_content is None:
            raise ValueError('Each media file entry must include path and content_base64.')

        try:
            content = base64.b64decode(encoded_content)
        except Exception as exc:
            raise ValueError(f'Invalid base64 payload for media file {relative_path}.') from exc

        target_path = os.path.join(settings.MEDIA_ROOT, *relative_path.split('/'))
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        summary['count'] += 1
        if os.path.exists(target_path):
            with open(target_path, 'rb') as existing_handle:
                if existing_handle.read() == content:
                    summary['skipped'] += 1
                    continue
            summary['updated'] += 1
        else:
            summary['created'] += 1

        with open(target_path, 'wb') as target_handle:
            target_handle.write(content)

    return summary


def _normalize_media_relative_path(path):
    if not path:
        return None

    normalized = str(path).replace('\\', '/').lstrip('/')
    parts = [part for part in normalized.split('/') if part]
    if not parts or any(part in {'.', '..'} for part in parts):
        raise ValueError(f'Invalid media file path: {path}')

    return '/'.join(parts)


def _serialize_value(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value) if value.__class__.__name__ == 'UUID' else value


def _get_concrete_field(model, field_name):
    for field in model._meta.concrete_fields:
        if field.name == field_name:
            return field
    return None


def _normalize_peer_url(peer_url):
    if not peer_url:
        return None
    return str(peer_url).rstrip('/')


def _build_peer_url(peer_url, path, query=None):
    normalized_url = _normalize_peer_url(peer_url)
    normalized_path = '/' + str(path).lstrip('/')
    url = normalized_url + normalized_path
    if query:
        encoded_query = urllib_parse.urlencode({key: value for key, value in query.items() if value not in (None, '')})
        if encoded_query:
            url = f'{url}?{encoded_query}'
    return url


def _get_peer_api_token(peer_url):
    normalized_url = _normalize_peer_url(peer_url)
    peer_tokens = getattr(settings, 'ETL_PEER_TOKENS', {}) or {}
    return peer_tokens.get(normalized_url) or getattr(settings, 'ETL_API_TOKEN', '')


def _extract_remote_error(exc):
    try:
        body = exc.read().decode('utf-8')
    except Exception:
        return exc.reason or 'Unknown remote error'

    if not body:
        return exc.reason or 'Unknown remote error'

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(payload, dict):
        return payload.get('detail') or payload.get('error') or body
    return body

