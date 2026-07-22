"""Read-only access to the controlled vocabularies.

Publishing these is the point of an interoperability API: another project can
align its own terms with ours and cite stable UUIDs. Writing is not offered —
vocabularies are curated inside eCatalogus.

The registry is an explicit allow-list rather than a sweep over
``MODEL_CATEGORIES``, so adding a model to the ETL config can never
accidentally publish it.
"""

from django.apps import apps

from etlapp.services import _serialize_instance

from .export import add_labels


DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 1000


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


def build_dictionary_page(slug, search=None, since=None, limit=None, offset=0):
    model, search_fields = get_dictionary_model(slug)
    if model is None:
        raise LookupError(f'Unknown dictionary "{slug}".')

    queryset = model.objects.all()

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
    add_labels(payload)

    return {
        'api_version': 'v1',
        'slug': slug,
        'model': model._meta.label,
        'count': total,
        'limit': limit,
        'offset': offset,
        'next_offset': offset + limit if offset + limit < total else None,
        'results': records,
    }
