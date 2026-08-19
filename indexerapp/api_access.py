"""Shared authorisation primitives for every write-capable HTTP entry point.

Historically the bulk import views and the DataTables ``ModelViewSet``s were
reachable without any authentication at all. Everything that can change data now
routes its decision through :func:`user_can_write_api` so there is exactly one
place to reason about.

Read access stays open — the catalogue is meant to be public.
"""

from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.throttling import AnonRateThrottle

from etlapp.main_guard import (
    main_master_label,
    main_master_url,
    main_read_only_message,
    main_read_only_payload,
    main_writes_allowed,
)


API_IMPORTER_GROUP = 'api_importers'


class AnonExpensiveRateThrottle(AnonRateThrottle):
    """Tighter anonymous budget for endpoints that aggregate over whole tables.

    Inherits ``AnonRateThrottle``, so authenticated callers — ETL peers and
    integration accounts — are still exempt.
    """

    scope = 'anon_expensive'


def user_can_write_api(user, permissions=()):
    """Return True when ``user`` may create or modify catalogue data.

    Membership of the ``api_importers`` group grants blanket write access — that
    is how external systems such as ritus-indexer are onboarded. Otherwise the
    user must hold the Django model permissions the view declares, which keeps
    the existing editorial accounts working without any extra setup.
    """
    if not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'is_superuser', False):
        return True

    groups = getattr(user, 'groups', None)
    if groups is not None and groups.filter(name=API_IMPORTER_GROUP).exists():
        return True

    if not permissions:
        return False

    return user.has_perms([f'indexerapp.{permission}' for permission in permissions])


class PublicReadOrEditorWrite(BasePermission):
    """Anonymous reads, authorised writes.

    Installed as ``DEFAULT_PERMISSION_CLASSES`` so a viewset that forgets to
    declare its own policy fails closed on writes instead of open.
    """

    message = 'You do not have permission to modify catalogue data.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return user_can_write_api(request.user, getattr(view, 'required_permissions', ()))


class EditorWriteOnly(BasePermission):
    """Every method — including reads — requires an authorised editor."""

    message = 'You do not have permission to access this endpoint.'

    def has_permission(self, request, view):
        return user_can_write_api(request.user, getattr(view, 'required_permissions', ()))


class EditorRequiredMixin:
    """Authorisation gate for the plain ``django.views.View`` import endpoints.

    Subclasses set ``required_permissions`` to the Django permission codenames
    that correspond to the table they write into.
    """

    required_permissions = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': 'Authentication required.'}, status=401)

        if not user_can_write_api(request.user, self.required_permissions):
            return JsonResponse({'detail': 'Insufficient permissions to import data.'}, status=403)

        return super().dispatch(request, *args, **kwargs)


class EditorRequiredForWriteMixin(EditorRequiredMixin):
    """Same gate, but only for methods that can change data."""

    def dispatch(self, request, *args, **kwargs):
        if request.method in SAFE_METHODS:
            return super(EditorRequiredMixin, self).dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)


def main_read_only_response(request, subject=None):
    """Full-page explanation for browser surfaces such as the iommi admin.

    The JSON endpoints answer with :func:`main_read_only_payload` instead; this
    one exists because a bare 403 or 404 in a form-based admin tells the editor
    nothing about where the entry actually belongs.
    """
    subject = subject or 'This reference table'
    return render(
        request,
        'main_read_only.html',
        {
            'subject': subject,
            'message': main_read_only_message(subject),
            'main_master': main_master_label(),
            'main_master_url': main_master_url(),
        },
        status=403,
    )


class MainMasterOnlyMixin:
    """Refuses writes to ``main`` reference tables outside eCatalogus.

    Mix it in *after* :class:`EditorRequiredMixin` so an anonymous caller still
    gets 401 rather than the read-only explanation, which would otherwise leak
    which tables exist to callers who cannot write anywhere.
    """

    #: Human-readable name of the table, used to open the refusal message.
    main_subject = 'This reference table'

    def dispatch(self, request, *args, **kwargs):
        if request.method not in SAFE_METHODS and not main_writes_allowed():
            return JsonResponse(main_read_only_payload(self.main_subject), status=403)
        return super().dispatch(request, *args, **kwargs)
