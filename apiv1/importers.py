"""Write side of the public API: transactional bulk content import.

The rules that make this safe to expose to a foreign system:

* the whole payload is validated before a single row is written;
* the write runs inside one transaction, so a failure leaves nothing behind;
* every rejected row is reported with its index, field and offending value;
* dictionary entries are never created implicitly — an unknown liturgical genre
  is an error, not a silent new dictionary row.

That last rule is deliberate. Letting an external system invent dictionary
entries is how controlled vocabularies rot.
"""

import uuid as uuid_module

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Max

from indexerapp.models import Content, Manuscripts

from .content_fields import (
    ALL_KEYS,
    IGNORED_INPUT_KEYS,
    MANUSCRIPT_ALL_KEYS,
    MANUSCRIPT_IGNORED_INPUT_KEYS,
    MANUSCRIPT_PLAIN_FIELDS,
    MANUSCRIPT_RELATION_FIELDS,
    PLAIN_FIELDS,
    RELATION_FIELDS,
)


MAX_ERRORS_REPORTED = 200


class ImportValidationError(Exception):
    """Raised when the payload as a whole cannot be accepted."""

    def __init__(self, detail, errors=None):
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or []


def _looks_like_uuid(value):
    try:
        uuid_module.UUID(str(value).strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return True


class _RelationResolver:
    """Resolves dictionary references, caching every lookup for the batch.

    ``manuscript`` is needed only by the manuscript-scoped relations — a content
    row's music notation is one of *that manuscript's* notation blocks, not an
    entry in a shared vocabulary.
    """

    def __init__(self, manuscript=None):
        self._cache = {}
        self._manuscript = manuscript

    def resolve(self, spec, raw_value):
        """Return the related row's UUID, or raise ``LookupError``."""
        text = str(raw_value).strip()
        cache_key = (spec.key, text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        model = apps.get_model('indexerapp', spec.model)

        instance = None
        if _looks_like_uuid(text):
            instance = model.objects.filter(uuid=uuid_module.UUID(text)).only('uuid').first()

        if instance is None and spec.key == 'edition_index':
            instance = self._resolve_edition_index(model, text)

        if instance is None and spec.key == 'music_notation_id':
            instance = self._resolve_music_notation(model, text)

        if instance is None:
            for lookup in spec.lookups:
                instance = model.objects.filter(**{f'{lookup}__iexact': text}).only('uuid').first()
                if instance is not None:
                    break

        if instance is None:
            hint = ' or '.join(spec.lookups) if spec.lookups else 'uuid'
            raise LookupError(
                f'No {spec.model} entry matches "{text}" (matched against: {hint}). '
                f'Dictionary entries must exist before content referencing them is imported.'
            )

        self._cache[cache_key] = instance.uuid
        return instance.uuid

    def _resolve_music_notation(self, model, text):
        """Accept a notation *name* and find this manuscript's block using it.

        ``Content.music_notation_uuid`` points at a ManuscriptMusicNotations row —
        one notated stretch of one manuscript, with its own folio range — while a
        foreign system typically records only which notation the item is written
        in. Translating between the two is possible exactly once the manuscript's
        notation has been described here, and never by inventing the description.
        """
        if self._manuscript is None:
            return None

        names = apps.get_model('indexerapp', 'MusicNotationNames')
        name_row = None
        if _looks_like_uuid(text):
            name_row = names.objects.filter(uuid=uuid_module.UUID(text)).only('uuid').first()
        if name_row is None:
            name_row = names.objects.filter(name__iexact=text).only('uuid').first()
        if name_row is None:
            return None

        block = (
            model.objects
            .filter(
                manuscript_uuid=self._manuscript,
                music_notation_name_uuid_id=name_row.uuid,
            )
            .order_by('sequence_in_ms', 'pk')
            .only('uuid')
            .first()
        )
        if block is None:
            raise LookupError(
                f'"{text}" is a known music notation, but "{self._manuscript.name}" has no '
                'notation described with it. A content row can only point at one of the '
                "manuscript's own notation records — add the notation to the manuscript "
                'first, or omit music_notation_id.'
            )
        return block

    @staticmethod
    def _resolve_edition_index(model, text):
        """Accept the editorial ``"<bibliography shortname> c.<sequence>"`` form."""
        if ' c.' not in text:
            return None
        shortname, _, sequence = text.partition(' c.')
        return (
            model.objects
            .filter(
                bibliography_uuid__shortname__iexact=shortname.strip(),
                feast_rubric_sequence=sequence.strip(),
            )
            .only('uuid')
            .first()
        )


def _coerce_plain(spec, raw_value):
    if raw_value is None or raw_value == '':
        return None

    if spec.kind == 'int':
        try:
            return int(str(raw_value).strip())
        except (TypeError, ValueError):
            raise ValueError(f'expected a whole number, got "{raw_value}"') from None

    if spec.kind == 'bool':
        text = str(raw_value).strip().lower()
        if text in {'1', 'true', 'yes'}:
            return True
        if text in {'0', 'false', 'no'}:
            return False
        raise ValueError(f'expected a boolean, got "{raw_value}"')

    return raw_value


def _validate_rows(rows, resolver, strict_keys):
    """Turn raw JSON rows into model kwargs, collecting every problem found."""
    prepared = []
    errors = []

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append({
                'row': index,
                'field': None,
                'value': None,
                'error': 'invalid_row',
                'detail': 'Each item must be a JSON object.',
            })
            continue

        attrs = {}

        if strict_keys:
            for key in row:
                if key not in ALL_KEYS and key not in IGNORED_INPUT_KEYS:
                    errors.append({
                        'row': index,
                        'field': key,
                        'value': row.get(key),
                        'error': 'unknown_field',
                        'detail': f'"{key}" is not a recognised content field.',
                    })

        for spec in PLAIN_FIELDS:
            if spec.key not in row:
                continue
            try:
                attrs[spec.attr] = _coerce_plain(spec, row[spec.key])
            except ValueError as exc:
                errors.append({
                    'row': index,
                    'field': spec.key,
                    'value': row[spec.key],
                    'error': 'invalid_value',
                    'detail': str(exc),
                })

        for spec in RELATION_FIELDS:
            if spec.key not in row:
                continue
            raw_value = row[spec.key]
            if raw_value is None or str(raw_value).strip() == '':
                attrs[f'{spec.attr}_id'] = None
                continue
            try:
                attrs[f'{spec.attr}_id'] = resolver.resolve(spec, raw_value)
            except LookupError as exc:
                errors.append({
                    'row': index,
                    'field': spec.key,
                    'value': raw_value,
                    'error': 'not_found',
                    'detail': str(exc),
                })

        # Non-nullable columns that the model declares with a "" default.
        for column in ('where_in_ms_from', 'where_in_ms_to'):
            if attrs.get(column) is None:
                attrs[column] = ''

        prepared.append(attrs)

        if len(errors) >= MAX_ERRORS_REPORTED:
            errors.append({
                'row': index,
                'field': None,
                'value': None,
                'error': 'too_many_errors',
                'detail': f'Reporting stopped after {MAX_ERRORS_REPORTED} problems.',
            })
            break

    return prepared, errors


def _next_sequence_start(manuscript):
    current_max = (
        Content.objects.filter(manuscript_uuid=manuscript)
        .aggregate(value=Max('sequence_in_ms'))['value']
    )
    return (current_max or 0) + 1


def import_content_bulk(manuscript, rows, mode='append', dry_run=False, strict_keys=True):
    """Import a batch of content rows for one manuscript.

    ``mode='replace'`` deletes the manuscript's existing content first; use it
    for a re-upload after corrections. ``mode='append'`` is the default and only
    ever adds.
    """
    if mode not in {'append', 'replace'}:
        raise ImportValidationError(f'Unknown mode "{mode}". Use "append" or "replace".')

    if not isinstance(rows, list):
        raise ImportValidationError('"items" must be a list of content objects.')

    if not rows:
        raise ImportValidationError('"items" is empty — nothing to import.')

    resolver = _RelationResolver(manuscript=manuscript)
    prepared, errors = _validate_rows(rows, resolver, strict_keys)

    if errors:
        raise ImportValidationError(
            f'{len(errors)} problem(s) found; nothing was imported.',
            errors=errors,
        )

    report = {
        'api_version': 'v1',
        'site_name': getattr(settings, 'SITE_NAME', ''),
        'manuscript_uuid': str(manuscript.uuid) if manuscript.uuid else None,
        'manuscript_name': manuscript.name,
        'mode': mode,
        'dry_run': dry_run,
        'received': len(rows),
        'created': 0,
        'deleted': 0,
        'errors': [],
    }

    if dry_run:
        report['detail'] = 'Payload is valid. Nothing was written because dry_run was set.'
        return report

    with transaction.atomic():
        if mode == 'replace':
            deleted, _ = Content.objects.filter(manuscript_uuid=manuscript).delete()
            report['deleted'] = deleted

        next_sequence = _next_sequence_start(manuscript)
        created_uuids = []

        for offset, attrs in enumerate(prepared):
            # Always set both sequence columns explicitly: their model default is
            # a callable that runs an aggregate query on every instantiation.
            if attrs.get('sequence_in_ms') is None:
                attrs['sequence_in_ms'] = next_sequence + offset
            attrs.setdefault('rubric_sequence', None)

            content = Content(manuscript_uuid=manuscript, **attrs)
            content.save()
            created_uuids.append(str(content.uuid) if content.uuid else None)

        report['created'] = len(created_uuids)
        report['created_uuids'] = created_uuids

    return report


def create_manuscript(data, strict_keys=True):
    """Create one manuscript from a flat JSON object.

    Same contract as the bulk content import: validate everything, name every
    problem, write nothing on failure.
    """
    if not isinstance(data, dict):
        raise ImportValidationError('Expected a JSON object describing the manuscript.')

    errors = []
    attrs = {}

    if strict_keys:
        for key in data:
            if key not in MANUSCRIPT_ALL_KEYS and key not in MANUSCRIPT_IGNORED_INPUT_KEYS:
                errors.append({
                    'row': 0,
                    'field': key,
                    'value': data.get(key),
                    'error': 'unknown_field',
                    'detail': f'"{key}" is not a recognised manuscript field.',
                })

    name = (data.get('name') or '').strip()
    if not name:
        errors.append({
            'row': 0,
            'field': 'name',
            'value': data.get('name'),
            'error': 'required',
            'detail': '"name" is required and cannot be blank.',
        })

    for spec in MANUSCRIPT_PLAIN_FIELDS:
        if spec.key not in data:
            continue
        try:
            attrs[spec.attr] = _coerce_plain(spec, data[spec.key])
        except ValueError as exc:
            errors.append({
                'row': 0,
                'field': spec.key,
                'value': data[spec.key],
                'error': 'invalid_value',
                'detail': str(exc),
            })

    resolver = _RelationResolver()
    for spec in MANUSCRIPT_RELATION_FIELDS:
        if spec.key not in data:
            continue
        raw_value = data[spec.key]
        if raw_value is None or str(raw_value).strip() == '':
            attrs[f'{spec.attr}_id'] = None
            continue
        try:
            attrs[f'{spec.attr}_id'] = resolver.resolve(spec, raw_value)
        except LookupError as exc:
            errors.append({
                'row': 0,
                'field': spec.key,
                'value': raw_value,
                'error': 'not_found',
                'detail': str(exc),
            })

    if errors:
        raise ImportValidationError(
            f'{len(errors)} problem(s) found; the manuscript was not created.',
            errors=errors,
        )

    # A manuscript arriving through the API is a real catalogue entry; without
    # this it would be invisible to the content endpoints, which filter on it.
    attrs.setdefault('display_as_main', True)

    with transaction.atomic():
        manuscript = Manuscripts(**attrs)
        manuscript.save()

    return manuscript
