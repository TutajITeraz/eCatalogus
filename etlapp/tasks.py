from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.apps import apps

from .services import (
    pull_remote_category,
    pull_remote_manuscript,
    import_delta_payload,
    import_manuscript_payload,
    build_delta_export_payload,
    build_manuscript_export_payload,
)


def get_database_stats():
    """Zwraca nazwę bazy danych oraz liczebność rekordów w głównych tabelach."""
    db_name = connection.settings_dict.get('NAME', 'unknown')

    # Zbieramy liczebność dla wszystkich modeli w aplikacji (lub wybranych)
    model_counts = {}
    for model in apps.get_models():
        try:
            # Pomijamy modele systemowe Django
            if model._meta.app_label in ['auth', 'contenttypes', 'sessions', 'admin']:
                continue
            count = model.objects.count()
            model_counts[f"{model._meta.app_label}.{model._meta.model_name}"] = count
        except Exception:
            # Na wypadek problemów z tabelą
            pass

    return {
        'database_name': db_name,
        'table_counts': model_counts,
        'total_records': sum(model_counts.values())
    }


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
        stats = get_database_stats()
        return {
            'status': 'success',
            'result': result,
            'database_stats': stats
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
        stats = get_database_stats()
        return {
            'status': 'success',
            'result': result,
            'database_stats': stats
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
        stats = get_database_stats()
        return {
            'status': 'success',
            'result': result,
            'database_stats': stats
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
        stats = get_database_stats()
        return {
            'status': 'success',
            'result': result,
            'database_stats': stats
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
        stats = get_database_stats()
        return {
            'status': 'success',
            'payload': payload,
            'database_stats': stats
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
        stats = get_database_stats()
        return {
            'status': 'success',
            'payload': payload,
            'database_stats': stats
        }
    except Exception as exc:
        return {
            'status': 'failed',
            'error': str(exc)
        }