import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from pyzotero import zotero

from .models import Bibliography, ManuscriptBibliography, Manuscripts


class ZoteroConfigurationError(ImproperlyConfigured):
    pass


def get_zotero_config():
    library_id = str(getattr(settings, 'ZOTERO_LIBRARY_ID', '') or '').strip()
    api_key = str(getattr(settings, 'ZOTERO_API_KEY', '') or '').strip()
    library_type = str(getattr(settings, 'ZOTERO_LIBRARY_TYPE', 'group') or 'group').strip() or 'group'
    bibliography_style = str(
        getattr(
            settings,
            'ZOTERO_BIBLIOGRAPHY_STYLE',
            'https://www.zotero.org/styles/pontifical-biblical-institute',
        )
        or ''
    ).strip()

    missing = []
    if not library_id:
        missing.append('ZOTERO_LIBRARY_ID')
    if not api_key:
        missing.append('ZOTERO_API_KEY')
    if missing:
        raise ZoteroConfigurationError(
            'Missing Zotero configuration: ' + ', '.join(missing)
        )

    return {
        'library_id': library_id,
        'library_type': library_type,
        'api_key': api_key,
        'bibliography_style': bibliography_style,
    }


def get_zotero_client():
    config = get_zotero_config()
    return zotero.Zotero(config['library_id'], config['library_type'], config['api_key'])


def list_zotero_nodes(parent_collection_key=None, current_hierarchy=0):
    zot_client = get_zotero_client()
    if parent_collection_key:
        collections = zot_client.everything(zot_client.collections_sub(parent_collection_key))
        items = zot_client.everything(zot_client.collection_items_top(parent_collection_key))
    else:
        collections = zot_client.everything(zot_client.collections_top())
        items = []

    nodes = [
        _serialize_collection_node(collection, hierarchy=current_hierarchy + 1)
        for collection in collections
    ]
    nodes.extend(
        _serialize_item_node(item, hierarchy=current_hierarchy)
        for item in items
        if _is_importable_item(item)
    )
    return nodes


def list_zotero_collection_items(collection_key, current_hierarchy=0):
    zot_client = get_zotero_client()
    return _collect_collection_items_recursive(
        zot_client,
        collection_key,
        current_hierarchy=current_hierarchy,
    )


def import_zotero_items(manuscript_selector, selected_items):
    manuscript = _resolve_manuscript(manuscript_selector)
    normalized_items = _normalize_selected_items(selected_items)
    if not normalized_items:
        raise ValueError('No Zotero items selected for import.')

    zot_client = get_zotero_client()
    summary = {
        'manuscript_uuid': str(manuscript.uuid) if manuscript.uuid else None,
        'manuscript_label': str(manuscript),
        'selected_count': len(normalized_items),
        'bibliography_created': 0,
        'bibliography_updated': 0,
        'links_created': 0,
        'links_existing': 0,
        'items': [],
    }

    for selected_item in normalized_items:
        zotero_key = selected_item['key']
        item_payload = zot_client.item(zotero_key)
        if not _is_importable_item(item_payload):
            continue

        mapped_fields = map_zotero_item_to_bibliography(
            item_payload,
            hierarchy=selected_item.get('hierarchy'),
        )
        bibliography, was_created, was_updated = _get_or_create_bibliography(mapped_fields)
        relation, relation_created = ManuscriptBibliography.objects.get_or_create(
            manuscript_uuid=manuscript,
            bibliography_uuid=bibliography,
        )

        if was_created:
            summary['bibliography_created'] += 1
        if was_updated:
            summary['bibliography_updated'] += 1
        if relation_created:
            summary['links_created'] += 1
        else:
            summary['links_existing'] += 1

        summary['items'].append(
            {
                'zotero_key': zotero_key,
                'title': bibliography.title,
                'bibliography_uuid': str(bibliography.uuid) if bibliography.uuid else None,
                'relation_uuid': str(relation.uuid) if relation.uuid else None,
                'created_bibliography': was_created,
                'updated_bibliography': was_updated,
                'created_relation': relation_created,
            }
        )

    return summary


def map_zotero_item_to_bibliography(item_payload, hierarchy=None):
    data = item_payload.get('data', {})
    title = _clean_text(data.get('title')) or _clean_text(data.get('shortTitle')) or f"Zotero item {data.get('key', '')}".strip()
    author = _truncate(_format_creators(data.get('creators', [])), 128)
    shortname = _truncate(_build_shortname(data, title, author), 5)
    year = _extract_year(data.get('date'))

    mapped = {
        'title': _truncate(title, 128),
        'author': author,
        'shortname': shortname,
        'year': year,
        'zotero_id': _clean_text(data.get('key')),
        'hierarchy': hierarchy if hierarchy not in (None, '') else None,
    }
    return mapped


def render_bibliography_entries(entries, *, content, format_name=None):
    zot_client = get_zotero_client()
    rendered = []

    for bibliography_link in entries:
        bibliography = bibliography_link.bibliography
        if bibliography is None or not bibliography.zotero_id:
            continue

        if content == 'bib,html':
            item = zot_client.item(
                bibliography.zotero_id,
                limit=50,
                content=content,
                format=format_name,
            )
        else:
            item = zot_client.item(
                bibliography.zotero_id,
                limit=50,
                content=content,
            )
        rendered.append(item[0])

    return rendered


def _resolve_manuscript(manuscript_selector):
    if manuscript_selector in (None, ''):
        raise ValueError('Missing manuscript selector.')

    manuscript = Manuscripts.objects.filter(uuid=manuscript_selector).first()
    if manuscript is None:
        manuscript = Manuscripts.objects.filter(pk=manuscript_selector).first()
    if manuscript is None:
        raise ValueError('Selected manuscript does not exist.')
    return manuscript


def _normalize_selected_items(selected_items):
    normalized = []
    seen = set()

    for item in selected_items or []:
        if isinstance(item, dict):
            key = _clean_text(item.get('key'))
            hierarchy = item.get('hierarchy')
        else:
            key = _clean_text(item)
            hierarchy = None

        if not key or key in seen:
            continue

        seen.add(key)
        normalized.append(
            {
                'key': key,
                'hierarchy': _coerce_int(hierarchy),
            }
        )

    return normalized


def _get_or_create_bibliography(mapped_fields):
    bibliography = None
    zotero_id = mapped_fields.get('zotero_id')
    if zotero_id:
        bibliography = Bibliography.objects.filter(zotero_id__iexact=zotero_id).first()

    if bibliography is None:
        bibliography = Bibliography.objects.filter(
            title__iexact=mapped_fields['title'],
            author__iexact=(mapped_fields.get('author') or ''),
            year=mapped_fields.get('year'),
        ).first()

    if bibliography is None:
        bibliography = Bibliography.objects.create(**mapped_fields)
        return bibliography, True, False

    updated = False
    for field_name, value in mapped_fields.items():
        current_value = getattr(bibliography, field_name)
        if current_value in (None, '') and value not in (None, ''):
            setattr(bibliography, field_name, value)
            updated = True

    if updated:
        bibliography.save()

    return bibliography, False, updated


def _serialize_collection_node(collection_payload, hierarchy):
    data = collection_payload.get('data', {})
    meta = collection_payload.get('meta', {})
    return {
        'node_type': 'collection',
        'key': data.get('key'),
        'label': data.get('name') or 'Untitled collection',
        'hierarchy': hierarchy,
        'child_collection_count': meta.get('numCollections', 0),
        'child_item_count': meta.get('numItems', 0),
        'has_children': bool(meta.get('numCollections', 0) or meta.get('numItems', 0)),
    }


def _serialize_item_node(item_payload, hierarchy):
    data = item_payload.get('data', {})
    return {
        'node_type': 'item',
        'key': data.get('key'),
        'label': _clean_text(data.get('title')) or _clean_text(data.get('shortTitle')) or 'Untitled item',
        'hierarchy': hierarchy,
        'item_type': data.get('itemType'),
        'author': _format_creators(data.get('creators', [])),
        'year': _extract_year(data.get('date')),
    }


def _collect_collection_items_recursive(zot_client, collection_key, current_hierarchy=0):
    item_nodes = [
        _serialize_item_node(item, hierarchy=current_hierarchy)
        for item in zot_client.everything(zot_client.collection_items_top(collection_key))
        if _is_importable_item(item)
    ]

    child_collections = zot_client.everything(zot_client.collections_sub(collection_key))
    for child_collection in child_collections:
        child_key = child_collection.get('data', {}).get('key')
        if not child_key:
            continue
        item_nodes.extend(
            _collect_collection_items_recursive(
                zot_client,
                child_key,
                current_hierarchy=current_hierarchy + 1,
            )
        )

    return item_nodes


def _is_importable_item(item_payload):
    data = item_payload.get('data', {})
    return data.get('itemType') not in {'attachment', 'note', 'annotation'}


def _format_creators(creators):
    names = []
    for creator in creators or []:
        label = _creator_label(creator)
        if label:
            names.append(label)
    return _truncate('; '.join(names), 128)


def _creator_label(creator):
    if not isinstance(creator, dict):
        return ''

    if creator.get('name'):
        return _clean_text(creator.get('name'))

    first_name = _clean_text(creator.get('firstName'))
    last_name = _clean_text(creator.get('lastName'))
    if first_name and last_name:
        return f'{last_name}, {first_name}'
    return last_name or first_name or ''


def _build_shortname(data, title, author):
    short_title = _clean_text(data.get('shortTitle'))
    if short_title:
        return short_title

    if author:
        compact_author = re.sub(r'[^A-Za-z0-9]', '', author)
        if compact_author:
            return compact_author[:5]

    compact_title = re.sub(r'[^A-Za-z0-9]', '', title or '')
    return compact_title[:5] or None


def _extract_year(raw_date):
    if not raw_date:
        return None

    match = re.search(r'(1\d{3}|20\d{2})', str(raw_date))
    if not match:
        return None
    return int(match.group(1))


def _truncate(value, limit):
    if value in (None, ''):
        return None
    return str(value)[:limit]


def _clean_text(value):
    if value in (None, ''):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None