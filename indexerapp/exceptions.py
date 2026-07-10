from django.db.models.deletion import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as default_exception_handler


def _describe(obj):
    try:
        label = str(obj)
    except Exception:
        label = f"{type(obj).__name__}#{obj.pk}"
    identifier = getattr(obj, 'uuid', None) or obj.pk
    return {'id': str(identifier), 'label': label}


def custom_exception_handler(exc, context):
    """Turns a PROTECT-blocked delete into a JSON response listing what's blocking it.

    Django admin already renders its own page for ProtectedError/RestrictedError;
    this covers the DRF API side of the same on_delete=PROTECT fields.
    """
    if isinstance(exc, (ProtectedError, RestrictedError)):
        protected_objects = list(
            getattr(exc, 'protected_objects', None) or getattr(exc, 'restricted_objects', [])
        )

        by_model = {}
        for obj in protected_objects:
            by_model.setdefault(type(obj).__name__, []).append(_describe(obj))

        blocked_by = [
            {'model': model_name, 'count': len(items), 'examples': items[:20]}
            for model_name, items in by_model.items()
        ]
        total = sum(entry['count'] for entry in blocked_by)

        return Response(
            {
                'error': 'cannot_delete_in_use',
                'detail': (
                    f"Cannot delete: this record is still referenced by {total} other "
                    f"record(s). Remove or reassign those references first."
                ),
                'blocked_by': blocked_by,
            },
            status=status.HTTP_409_CONFLICT,
        )

    return default_exception_handler(exc, context)
