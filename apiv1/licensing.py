"""Rights, attribution and citation metadata for everything the API hands out.

The practice this implements, which is what digital humanities consumers expect:

1. **Signal the licence at the transport layer** — a ``Link: <url>; rel="license"``
   header (RFC 8288) on every response, so the terms travel with the bytes even
   if the payload is split, cached or proxied.
2. **Repeat it inside the payload** — a ``rights`` block, because JSON gets saved
   to a file and the headers are lost the moment it does.
3. **Name the people, not just the institution** — CC BY obliges the reuser to
   credit; they can only do that if the export tells them whom to credit. The
   contributors are collected from the records actually present in the export.
4. **Offer a citation string** — scholars cite. If we do not supply the wording,
   we get cited inconsistently or not at all.

Field names follow Dublin Core and schema.org so they line up with vocabularies
other systems already parse.
"""

from django.conf import settings
from django.utils import timezone

from indexerapp.models import Contributors


LICENSE_LINK_REL = 'license'


def get_license():
    return getattr(settings, 'DATA_LICENSE', {}) or {}


def license_url():
    return get_license().get('url', '')


def _format_person(contributor):
    name = f'{contributor.first_name} {contributor.last_name}'.strip()
    return name or contributor.initials or str(contributor)


def collect_contributors(payload):
    """Gather everyone credited by the records inside an export package.

    Walks the serialized blocks rather than the database so the credit list
    describes exactly what the caller received — no more, no less.
    """
    contributor_uuids = set()
    contributor_pks = set()

    for model_block in payload.get('models', []):
        for record in model_block.get('results', []):
            data_contributor = record.get('data_contributor_uuid')
            if data_contributor:
                contributor_uuids.add(str(data_contributor))

            for author_pk in record.get('authors') or []:
                contributor_pks.add(author_pk)

    if not contributor_uuids and not contributor_pks:
        return []

    from django.db.models import Q

    predicate = Q()
    if contributor_uuids:
        predicate |= Q(uuid__in=contributor_uuids)
    if contributor_pks:
        predicate |= Q(pk__in=contributor_pks)

    people = Contributors.objects.filter(predicate).order_by('last_name', 'first_name')

    return [
        {
            'uuid': str(person.uuid) if person.uuid else None,
            'name': _format_person(person),
            'initials': person.initials,
            'affiliation': person.affiliation or None,
            'url': person.url or None,
        }
        for person in people
    ]


def build_rights(*, source_url=None, title=None, contributors=None):
    """The ``rights`` block attached to every public API response."""
    licence = get_license()
    accessed = timezone.now()

    credited = [person['name'] for person in (contributors or [])]

    # Reads as: "Graduale Cracoviense", contributed by A, B. Data from … CC BY 4.0.
    subject = f'"{title}"' if title else ''
    if credited:
        credit = 'contributed by ' + ', '.join(credited)
        subject = f'{subject}, {credit}' if subject else credit.capitalize()

    attribution = '. '.join(
        part for part in (subject, licence.get('required_statement', '')) if part
    ).strip()

    rights = {
        'license': licence.get('id'),
        'license_name': licence.get('name'),
        'license_url': licence.get('url'),
        'copyright': licence.get('copyright'),
        'rights_holder': licence.get('rights_holder'),
        'rights_holder_url': licence.get('rights_holder_url'),
        'required_statement': licence.get('required_statement'),
        'attribution': attribution,
        'accessed': accessed.isoformat(),
        'source': source_url,
        'recommended_citation': build_citation(
            title=title,
            contributors=credited,
            source_url=source_url,
            accessed=accessed,
        ),
    }

    if contributors is not None:
        rights['contributors'] = contributors

    return rights


def build_citation(*, title, contributors, source_url, accessed):
    """A ready-to-paste citation, so we are cited the way we want to be."""
    licence = get_license()
    site_name = getattr(settings, 'SITE_NAME', 'eCatalogus')

    parts = []
    if contributors:
        parts.append(', '.join(contributors))
    if title:
        parts.append(f'"{title}"')
    parts.append(site_name)
    if licence.get('rights_holder'):
        parts.append(licence['rights_holder'])
    parts.append(f'accessed {accessed.date().isoformat()}')
    if source_url:
        parts.append(source_url)
    if licence.get('id'):
        parts.append(f"Licensed under {licence['id']}")

    return '. '.join(part for part in parts if part) + '.'


def attach_rights(payload, request=None, title=None, contributors=None):
    """Add the ``rights`` block to a payload about to be returned."""
    payload['rights'] = build_rights(
        source_url=request.build_absolute_uri() if request is not None else None,
        title=title,
        contributors=contributors,
    )
    return payload
