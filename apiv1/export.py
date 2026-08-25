"""Read side of the public API.

Two shapes are offered, because two very different consumers exist:

``full package``
    The complete ETL manuscript package — every model that hangs off the
    manuscript — optionally decorated with ``*_label`` keys so a foreign system
    can read it without first downloading every dictionary. Built by reusing
    :func:`etlapp.services.build_manuscript_export_payload` verbatim, so the two
    exports can never drift apart.

``content rows``
    A flat, human-readable table of the manuscript's content, in exactly the
    format the bulk importer accepts.
"""

from django.apps import apps
from django.conf import settings

from etlapp.services import build_manuscript_export_payload
from indexerapp.models import Content

from .content_fields import PLAIN_FIELDS, RELATION_FIELDS


#: Tried in order when we need a human-readable name for an arbitrary related row.
LABEL_FIELD_CANDIDATES = (
    'name',
    'title',
    'short_name',
    'shortname',
    'standard_incipit',
    'time_description',
    'repository_today_eng',
    'repository_today_local_language',
    'co_no',
    'initials',
    'text',
)


def object_label(instance, preferred_fields=()):
    """Best available human-readable rendering of a related row."""
    for field_name in tuple(preferred_fields) + LABEL_FIELD_CANDIDATES:
        value = getattr(instance, field_name, None)
        if value:
            text = str(value).strip()
            if text:
                return text[:200]
    return str(instance)


def _relation_fields(model):
    return [
        model_field
        for model_field in model._meta.concrete_fields
        if model_field.is_relation and model_field.many_to_one
    ]


def _label_key(field_name):
    base = field_name[:-5] if field_name.endswith('_uuid') else field_name
    return f'{base}_label'


def add_labels(payload):
    """Decorate an ETL package in place with ``*_label`` keys.

    Without this a consumer sees ``"place_of_origin_uuid": "9c61…"`` and has no
    way to render it. Labels are resolved with one query per foreign key per
    model, not one per row.
    """
    for model_block in payload.get('models', []):
        try:
            model = apps.get_model(model_block['model'])
        except LookupError:
            continue

        records = model_block.get('results', [])
        if not records:
            continue

        for model_field in _relation_fields(model):
            key = model_field.name
            target_attr = model_field.target_field.name

            wanted = {record.get(key) for record in records if record.get(key) is not None}
            if not wanted:
                continue

            related = model_field.related_model.objects.filter(**{f'{target_attr}__in': wanted})
            labels = {
                str(getattr(instance, target_attr)): object_label(instance)
                for instance in related
            }

            label_key = _label_key(key)
            for record in records:
                raw = record.get(key)
                if raw is not None:
                    record[label_key] = labels.get(str(raw))

        for model_field in model._meta.many_to_many:
            key = model_field.name
            wanted = {pk for record in records for pk in (record.get(key) or [])}
            if not wanted:
                continue

            labels = {
                instance.pk: object_label(instance)
                for instance in model_field.related_model.objects.filter(pk__in=wanted)
            }
            for record in records:
                record[f'{key}_labels'] = [
                    labels.get(pk) for pk in (record.get(key) or [])
                ]

    return payload


def strip_local_ids(payload):
    """Remove every instance-local primary key from an ETL package, in place.

    Each instance assigns its own autoincrement ids — replication matches rows by
    UUID and never copies the primary key — so `id` means something different on
    every server. Publishing it next to `uuid` invites a foreign system to key on
    it and silently resolve to the wrong row elsewhere, which is exactly what
    happened. The UUID forms carry the same information and travel.

    Raw many-to-many primary-key lists go too, wherever the `*_uuids` companion
    is present to replace them. Run this after :func:`add_labels`, which reads
    those lists to build `*_labels`.
    """
    for model_block in payload.get('models', []):
        for record in model_block.get('results', []):
            record.pop('id', None)
            for key in [name for name in record if f'{name}_uuids' in record]:
                record.pop(key, None)

    return payload


def build_manuscript_package(manuscript_uuid, with_labels=True):
    """Full manuscript export — everything the manuscript tab displays."""
    payload = build_manuscript_export_payload(manuscript_uuid)
    payload['api_version'] = 'v1'
    if with_labels:
        add_labels(payload)
    strip_local_ids(payload)
    return payload


def content_queryset(manuscript):
    related = [spec.attr for spec in RELATION_FIELDS]
    return (
        Content.objects.filter(manuscript_uuid=manuscript)
        .select_related(*related)
        .order_by('sequence_in_ms', 'pk')
    )


def serialize_content_row(content):
    """One content row in the same vocabulary the bulk importer accepts."""
    row = {
        'uuid': str(content.uuid) if content.uuid else None,
        'manuscript_uuid': str(content.manuscript_uuid_id) if content.manuscript_uuid_id else None,
    }

    for spec in PLAIN_FIELDS:
        row[spec.key] = getattr(content, spec.attr)

    for spec in RELATION_FIELDS:
        raw = getattr(content, f'{spec.attr}_id')
        row[spec.key] = str(raw) if raw else None

        related = getattr(content, spec.attr, None)
        row[spec.label_key] = object_label(related, spec.label_fields) if related else None

    row['entry_date'] = content.entry_date.isoformat() if content.entry_date else None
    return row


def build_content_summary(manuscript):
    """Cheap 'does this manuscript already have content?' probe.

    ritus-indexer calls this before uploading so it does not create duplicates.
    """
    queryset = Content.objects.filter(manuscript_uuid=manuscript)
    count = queryset.count()

    sequences = queryset.exclude(sequence_in_ms__isnull=True).order_by('sequence_in_ms')
    first = sequences.first()
    last = sequences.last()
    latest = queryset.order_by('-entry_date').first()

    return {
        'api_version': 'v1',
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'manuscript_uuid': str(manuscript.uuid) if manuscript.uuid else None,
        'manuscript_name': manuscript.name,
        'content_count': count,
        'has_content': count > 0,
        'sequence_in_ms_min': first.sequence_in_ms if first else None,
        'sequence_in_ms_max': last.sequence_in_ms if last else None,
        'last_modified': latest.entry_date.isoformat() if latest and latest.entry_date else None,
    }
