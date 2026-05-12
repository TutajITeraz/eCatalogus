from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError

from .services import (
    pull_remote_category,
    pull_remote_manuscript,
    import_delta_payload,
    import_manuscript_payload,
    build_delta_export_payload,
    build_manuscript_export_payload,
)


@shared_task(bind=True)
def pull_category_task(self, peer_url, category, since=None, force_remote_uuids=None, keep_local_uuids=None):
    """Background task for pulling a category from remote peer."""
    try:
        result = pull_remote_category(
            peer_url=peer_url,
            category=category,
            since=since,
            force_remote_uuids=force_remote_uuids,
            keep_local_uuids=keep_local_uuids
        )
        return {
            'status': 'success',
            'result': result
        }
    except Exception as exc:
        self.retry(countdown=60, max_retries=3, exc=exc)
        return {
            'status': 'failed',
            'error': str(exc)
        }


@shared_task(bind=True)
def pull_manuscript_task(self, peer_url, manuscript_uuid):
    """Background task for pulling a manuscript from remote peer."""
    try:
        result = pull_remote_manuscript(peer_url=peer_url, manuscript_uuid=manuscript_uuid)
        return {
            'status': 'success',
            'result': result
        }
    except Exception as exc:
        self.retry(countdown=60, max_retries=3, exc=exc)
        return {
            'status': 'failed',
            'error': str(exc)
        }


@shared_task(bind=True)
def import_bundle_task(self, category, payload, force_remote_uuids=None, keep_local_uuids=None):
    """Background task for importing a bundle payload."""
    try:
        result = import_delta_payload(
            category=category,
            payload=payload,
            force_remote_uuids=force_remote_uuids,
            keep_local_uuids=keep_local_uuids
        )
        return {
            'status': 'success',
            'result': result
        }
    except Exception as exc:
        self.retry(countdown=60, max_retries=3, exc=exc)
        return {
            'status': 'failed',
            'error': str(exc)
        }


@shared_task(bind=True)
def import_manuscript_bundle_task(self, payload):
    """Background task for importing a manuscript bundle."""
    try:
        result = import_manuscript_payload(payload=payload)
        return {
            'status': 'success',
            'result': result
        }
    except Exception as exc:
        self.retry(countdown=60, max_retries=3, exc=exc)
        return {
            'status': 'failed',
            'error': str(exc)
        }


@shared_task(bind=True)
def export_bundle_task(self, category, since=None):
    """Background task for exporting a bundle payload."""
    try:
        payload = build_delta_export_payload(category=category, since=since)
        return {
            'status': 'success',
            'payload': payload
        }
    except Exception as exc:
        return {
            'status': 'failed',
            'error': str(exc)
        }


@shared_task(bind=True)
def export_manuscript_bundle_task(self, manuscript_uuid):
    """Background task for exporting a manuscript bundle."""
    try:
        payload = build_manuscript_export_payload(manuscript_uuid=manuscript_uuid)
        return {
            'status': 'success',
            'payload': payload
        }
    except Exception as exc:
        return {
            'status': 'failed',
            'error': str(exc)
        }