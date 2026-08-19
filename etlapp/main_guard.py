"""Who may write ``main`` reference data.

eCatalogus is the single source of truth for every model in the ``main``
category — the controlled vocabularies listed in :mod:`etlapp.model_categories`.
Every other instance receives those tables through the one-way ETL pull and must
not edit them locally, for two reasons that both end in silent data loss:

* a local edit is overwritten without warning by the next ``Pull main
  dictionaries``, because conflict detection exists only for ``shared``
  (see ``_import_model_records`` in :mod:`etlapp.services`);
* a locally created row never travels back up, because ``main`` has no push
  path — so the instances quietly drift apart.

This module therefore blocks the *editorial* surfaces — Django admin, the iommi
admin, the bulk import endpoints — on every instance that is not the canonical
master. It deliberately leaves the ETL import path alone: ``mpl`` is both a
slave of eCatalogus and the parent peer of ``limbo``, so it has to keep writing
``main`` rows while relaying them downstream.
"""

import tomllib
from pathlib import Path

from django.conf import settings
from django.utils.html import format_html

from .model_categories import get_model_category


# Used when the instance registry is unavailable — a stand-alone checkout, a
# management command run with the base settings, or the test settings.
DEFAULT_MAIN_MASTER_ID = 'ecatalogus'
DEFAULT_MAIN_MASTER_URL = 'https://ecatalogus.ispan.pl'
DEFAULT_MAIN_MASTER_LABEL = 'eCatalogus'


class MainReadOnlyError(Exception):
    """Raised when a non-master instance tries to write ``main`` data."""

    def __init__(self, message, *, subject=None):
        super().__init__(message)
        self.subject = subject


def is_main_model(model_name):
    return get_model_category(model_name) == 'main'


def canonical_main_master_id():
    return getattr(settings, 'ETL_CANONICAL_MASTER_ID', '') or DEFAULT_MAIN_MASTER_ID


def _self_peer_id():
    return getattr(settings, 'ETL_SELF_PEER_ID', '') or getattr(settings, 'INSTANCE_SLUG', '')


def main_writes_allowed():
    """True when this instance may create or change ``main`` records locally.

    ``ETL_ALLOW_MAIN_EDITS`` is an explicit escape hatch — set it to True when
    a second instance is temporarily promoted to curate vocabularies, or to
    False to lock down an instance that does not identify itself in the
    registry.
    """
    override = getattr(settings, 'ETL_ALLOW_MAIN_EDITS', None)
    if override is not None:
        return bool(override)

    self_peer_id = _self_peer_id()
    if self_peer_id:
        return self_peer_id == canonical_main_master_id()

    # An instance that does not name itself (single-instance install, base
    # settings, tests) keeps its historical freedom unless the role says slave.
    return getattr(settings, 'ETL_ROLE', 'undefined') != 'slave'


def _registry_entry(peer_id):
    registry_path = getattr(settings, 'ETL_PEER_REGISTRY_PATH', None)
    if not registry_path:
        return {}

    path = Path(registry_path)
    if not path.exists():
        return {}

    try:
        with path.open('rb') as handle:
            payload = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError):
        return {}

    instances = payload.get('instances', {}) or {}
    return instances.get(peer_id, {}) or {}


def main_master_url():
    """Public URL of the instance where ``main`` data is curated."""
    configured = getattr(settings, 'ETL_MAIN_MASTER_URL', '')
    if configured:
        return configured.rstrip('/')

    entry = _registry_entry(canonical_main_master_id())
    url = entry.get('public_url') or entry.get('etl_url') or DEFAULT_MAIN_MASTER_URL
    return url.rstrip('/')


def main_master_label():
    entry = _registry_entry(canonical_main_master_id())
    return entry.get('site_name') or DEFAULT_MAIN_MASTER_LABEL


def _local_label():
    return getattr(settings, 'SITE_NAME', '') or 'This instance'


def main_read_only_message(subject=None):
    """Plain-text explanation shown wherever a ``main`` write is refused."""
    subject = subject or 'This reference table'
    return (
        f'{subject} is a shared vocabulary curated centrally in {main_master_label()}. '
        f'{_local_label()} receives it read-only through the ETL sync, so it cannot be '
        f'added to or edited here — a local change would be overwritten by the next '
        f'"Pull main dictionaries" and would never reach the other instances. '
        f'Please make the change in {main_master_label()} at {main_master_url()}; '
        f'it will arrive here with the next sync.'
    )


def main_read_only_message_html(subject=None):
    """Same message, with the master instance rendered as a clickable link."""
    subject = subject or 'This reference table'
    url = main_master_url()
    return format_html(
        '{subject} is a shared vocabulary curated centrally in {master}. '
        '{local} receives it read-only through the ETL sync, so it cannot be added to '
        'or edited here — a local change would be overwritten by the next '
        '"Pull main dictionaries" and would never reach the other instances. '
        'Please make the change in '
        '<a href="{url}" target="_blank" rel="noopener">{url}</a>; '
        'it will arrive here with the next sync.',
        subject=subject,
        master=main_master_label(),
        local=_local_label(),
        url=url,
    )


def main_read_only_payload(subject=None):
    """JSON body for the import endpoints.

    ``info`` is what the importer UI prints; ``detail`` is what the rest of the
    API uses. Both carry the same sentence so neither caller has to special-case
    this response.
    """
    message = main_read_only_message(subject)
    return {
        'info': message,
        'detail': message,
        'read_only': True,
        'main_master': main_master_label(),
        'main_master_url': main_master_url(),
    }


def assert_main_writable(model_name, subject=None):
    """Raise :class:`MainReadOnlyError` if ``model_name`` may not be written here."""
    if not is_main_model(model_name) or main_writes_allowed():
        return
    raise MainReadOnlyError(main_read_only_message(subject), subject=subject)
