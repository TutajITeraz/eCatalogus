"""Read-only access to the controlled vocabularies.

Publishing these is the point of an interoperability API: another project can
align its own terms with ours and cite stable UUIDs. Writing is not offered —
vocabularies are curated inside eCatalogus.

The registry is an explicit allow-list rather than a sweep over
``MODEL_CATEGORIES``, so adding a model to the ETL config can never
accidentally publish it.
"""

import uuid as uuid_module

from django.apps import apps

from etlapp.services import _serialize_instance
from etlapp.uuid_utils import build_deterministic_sync_uuid

from .export import add_labels, strip_local_ids


DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 1000

#: Most a caller may name in one ``?uuids=`` / ``?legacy_ids=`` request.
MAX_SELECTED_KEYS = 1000

#: Dictionaries that also publish the local numeric ``id`` alongside ``uuid``.
#: Safe only for ``main``-category models whose id is kept identical across
#: instances by etlapp.services.MODELS_WITH_STABLE_ID and whose local editing
#: is blocked everywhere but the canonical master by etlapp/main_guard.py —
#: every other dictionary keeps the general "id means something different on
#: every instance" policy from strip_local_ids().
EXPOSE_LOCAL_ID_SLUGS = {'rite-names', 'formulas'}


#: slug -> (model name, columns searched by ?search=)
DICTIONARIES = {
    'rite-names': ('RiteNames', ('name', 'english_translation')),
    'liturgical-genres': ('LiturgicalGenres', ('title',)),
    'sections': ('Sections', ('name',)),
    'content-functions': ('ContentFunctions', ('name',)),
    'layers': ('Layer', ('short_name', 'name')),
    'mass-hours': ('MassHour', ('short_name', 'name')),
    'genres': ('Genre', ('short_name', 'name')),
    'seasons-and-months': ('SeasonMonth', ('short_name', 'name')),
    'weeks': ('Week', ('short_name', 'name')),
    'days': ('Day', ('short_name', 'name')),
    'feast-ranks': ('FeastRanks', ('name',)),
    'types': ('Type', ('short_name', 'name')),
    'topics': ('Topic', ('name',)),
    'ceremonies': ('Ceremony', ('name',)),
    'traditions': ('Traditions', ('name',)),
    'script-names': ('ScriptNames', ('name',)),
    'music-notation-names': ('MusicNotationNames', ('name',)),
    'time-reference': ('TimeReference', ('time_description',)),
    'places': ('Places', ('repository_today_eng', 'repository_today_local_language')),
    'colours': ('Colours', ('name',)),
    'subjects': ('Subjects', ('name',)),
    'characteristics': ('Characteristics', ('name',)),
    'decoration-types': ('DecorationTypes', ('name',)),
    'decoration-techniques': ('DecorationTechniques', ('name',)),
    'binding-types': ('BindingTypes', ('name',)),
    'binding-styles': ('BindingStyles', ('name',)),
    'binding-materials': ('BindingMaterials', ('name',)),
    'binding-decoration-types': ('BindingDecorationTypes', ('name',)),
    'binding-components': ('BindingComponents', ('name',)),
    'contributors': ('Contributors', ('initials', 'last_name', 'first_name')),
    'formulas': ('Formulas', ('co_no', 'text')),
    'text-standarization': ('TextStandarization', ('standard_incipit', 'cantus_id', 'usu_id')),
}


def get_dictionary_model(slug):
    entry = DICTIONARIES.get(slug)
    if entry is None:
        return None, ()
    model_name, search_fields = entry
    return apps.get_model('indexerapp', model_name), search_fields


def list_dictionaries(request_build_uri=None):
    results = []
    for slug in sorted(DICTIONARIES):
        model, _ = get_dictionary_model(slug)
        entry = {
            'slug': slug,
            'model': model._meta.label,
            'verbose_name': str(model._meta.verbose_name_plural),
            'count': model.objects.count(),
        }
        if request_build_uri is not None:
            entry['url'] = request_build_uri(f'/api/v1/dictionaries/{slug}/')
        results.append(entry)

    return {'api_version': 'v1', 'count': len(results), 'results': results}


class DictionaryQueryError(ValueError):
    """A malformed selector — reported as 400, not 404."""


def parse_uuid_list(raw):
    """Parse a ``?uuids=`` value into UUIDs, rejecting anything malformed."""
    wanted, invalid = [], []
    for token in str(raw).split(','):
        token = token.strip()
        if not token:
            continue
        try:
            wanted.append(uuid_module.UUID(token))
        except (ValueError, AttributeError, TypeError):
            invalid.append(token)

    if invalid:
        raise DictionaryQueryError(
            f'"uuids" contains {len(invalid)} value(s) that are not UUIDs: '
            + ', '.join(f'"{token}"' for token in invalid[:5])
        )
    if len(wanted) > MAX_SELECTED_KEYS:
        raise DictionaryQueryError(
            f'"uuids" names {len(wanted)} entries; at most {MAX_SELECTED_KEYS} per request.'
        )
    return wanted


def parse_legacy_id_list(raw):
    """Parse a ``?legacy_ids=`` value into integers, rejecting anything malformed."""
    wanted, invalid = [], []
    for token in str(raw).split(','):
        token = token.strip()
        if not token:
            continue
        try:
            wanted.append(int(token))
        except (TypeError, ValueError):
            invalid.append(token)

    if invalid:
        raise DictionaryQueryError(
            f'"legacy_ids" contains {len(invalid)} value(s) that are not whole numbers: '
            + ', '.join(f'"{token}"' for token in invalid[:5])
        )
    if len(wanted) > MAX_SELECTED_KEYS:
        raise DictionaryQueryError(
            f'"legacy_ids" names {len(wanted)} entries; at most {MAX_SELECTED_KEYS} per request.'
        )
    return wanted


def legacy_uuid_map(model, legacy_ids):
    """Map each legacy primary key to the UUID the migration derived from it.

    Rows carried over from the legacy database were given a UUID derived from
    their old primary key, which is the numbering foreign systems still hold.
    Entries created after that migration have random UUIDs and cannot be found
    this way — they come back in ``unresolved_legacy_ids`` instead.
    """
    label = model._meta.label
    return {
        legacy_id: build_deterministic_sync_uuid(label, legacy_id)
        for legacy_id in dict.fromkeys(legacy_ids)
    }


def project_fields(records, fields, always_keep=()):
    """Narrow each record to the requested columns."""
    if not fields:
        return records

    wanted = [name.strip() for name in str(fields).split(',') if name.strip()]
    if not wanted:
        return records

    keep = list(dict.fromkeys(list(always_keep) + wanted))
    return [
        {name: record[name] for name in keep if name in record}
        for record in records
    ]


def build_dictionary_page(
    slug, search=None, since=None, limit=None, offset=0,
    uuids=None, legacy_ids=None, fields=None,
):
    model, search_fields = get_dictionary_model(slug)
    if model is None:
        raise LookupError(f'Unknown dictionary "{slug}".')

    queryset = model.objects.all()

    uuid_to_legacy_id = {}
    unresolved_legacy_ids = []
    if legacy_ids is not None:
        derived = legacy_uuid_map(model, legacy_ids)
        uuid_to_legacy_id = {str(value): key for key, value in derived.items()}
        found = set(
            str(value) for value in
            model.objects.filter(uuid__in=derived.values()).values_list('uuid', flat=True)
        )
        unresolved_legacy_ids = [
            legacy_id for legacy_id, value in derived.items() if str(value) not in found
        ]
        queryset = queryset.filter(uuid__in=derived.values())

    if uuids is not None:
        queryset = queryset.filter(uuid__in=uuids)

    if search and search_fields:
        from django.db.models import Q

        predicate = Q()
        for field_name in search_fields:
            predicate |= Q(**{f'{field_name}__icontains': search})
        queryset = queryset.filter(predicate)

    if since and any(f.name == 'entry_date' for f in model._meta.concrete_fields):
        queryset = queryset.filter(entry_date__gte=since)

    total = queryset.count()

    limit = DEFAULT_PAGE_SIZE if limit is None else min(max(int(limit), 1), MAX_PAGE_SIZE)
    offset = max(int(offset or 0), 0)

    page = queryset.order_by('pk')[offset:offset + limit]
    records = [_serialize_instance(instance) for instance in page]

    payload = {
        'api_version': 'v1',
        'slug': slug,
        'models': [{'model': model._meta.label, 'results': records}],
    }
    preserved_ids = (
        [(record, record.get('id')) for record in records]
        if slug in EXPOSE_LOCAL_ID_SLUGS else None
    )

    add_labels(payload)

    # Labels are resolved from the raw many-to-many primary keys, so the local
    # ids can only be dropped once add_labels has run.
    strip_local_ids(payload)

    if preserved_ids is not None:
        for record, id_value in preserved_ids:
            record['id'] = id_value

    always_keep = ['uuid']
    if slug in EXPOSE_LOCAL_ID_SLUGS:
        always_keep.append('id')
    if uuid_to_legacy_id:
        for record in records:
            record['legacy_id'] = uuid_to_legacy_id.get(str(record.get('uuid')))
        always_keep.append('legacy_id')

    records = project_fields(records, fields, always_keep=always_keep)

    result = {
        'api_version': 'v1',
        'slug': slug,
        'model': model._meta.label,
        'count': total,
        'limit': limit,
        'offset': offset,
        'next_offset': offset + limit if offset + limit < total else None,
        'results': records,
    }

    if legacy_ids is not None:
        result['unresolved_legacy_ids'] = unresolved_legacy_ids

    return result
