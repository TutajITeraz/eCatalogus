import json

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ETLTokenAuthentication
from .schema import (
    ETL_MAIN_EXPORT_EXAMPLE,
    ETL_MANUSCRIPT_EXPORT_EXAMPLE,
    ETL_SHARED_CONFLICT_EXAMPLE,
    ETL_STATUS_EXAMPLE,
    ETLConflictResponseSerializer,
    ETLDeletedRecordsResponseSerializer,
    ETLDeltaExportResponseSerializer,
    ETLDeltaImportRequestSerializer,
    ETLDeltaImportResponseSerializer,
    ETLErrorSerializer,
    ETLManuscriptExportResponseSerializer,
    ETLManuscriptImportRequestSerializer,
    ETLManuscriptImportResponseSerializer,
    ETLManuscriptListResponseSerializer,
    ETLStatusResponseSerializer,
)
from .services import (
    ETLImportConflictError,
    build_deleted_records_payload,
    build_delta_export_payload,
    build_manuscript_export_payload,
    build_manuscript_list_payload,
    build_status_payload,
    fetch_remote_etl_json,
    get_etl_peer_configs,
    import_delta_payload,
    import_manuscript_payload,
    pull_remote_category,
    pull_remote_manuscript,
    resolve_shared_conflict,
    resolve_etl_peer,
    user_can_manage_etl,
)
from .tasks import (
    import_bundle_task,
    import_manuscript_bundle_task,
    pull_category_task,
    pull_manuscript_task,
)


class ETLHTMLJSONRenderer(BaseRenderer):
    media_type = 'text/html'
    format = 'html'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data, ensure_ascii=False, indent=2).encode(self.charset)


class ETLAPIView(APIView):
    authentication_classes = [ETLTokenAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, ETLHTMLJSONRenderer]


class ETLStatusView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='Get ETL instance status',
        responses={200: ETLStatusResponseSerializer, 401: ETLErrorSerializer},
        examples=[ETL_STATUS_EXAMPLE],
    )
    def get(self, request):
        return Response(build_status_payload())


class ETLDeletedRecordsView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='List deleted records for an ETL category',
        parameters=[
            OpenApiParameter(
                name='since',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Optional ISO 8601 date or datetime filter.',
                required=False,
            ),
        ],
        responses={200: ETLDeletedRecordsResponseSerializer, 400: ETLErrorSerializer, 404: ETLErrorSerializer},
    )
    def get(self, request, category):
        since_raw = request.query_params.get('since')
        since = None
        if since_raw:
            since = parse_datetime(since_raw)
            if since is None:
                parsed_date = parse_date(since_raw)
                if parsed_date is not None:
                    since = timezone.datetime.combine(parsed_date, timezone.datetime.min.time())
            if since is None:
                return Response(
                    {'detail': 'Invalid since value. Use ISO 8601 date or datetime.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            payload = build_deleted_records_payload(category=category, since=since)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(payload)


class ETLDeltaExportView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='Export ETL delta for a category',
        parameters=[
            OpenApiParameter(
                name='since',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Optional ISO 8601 date or datetime filter.',
                required=False,
            ),
        ],
        responses={200: ETLDeltaExportResponseSerializer, 400: ETLErrorSerializer, 404: ETLErrorSerializer},
        examples=[ETL_MAIN_EXPORT_EXAMPLE],
    )
    def get(self, request, category):
        since_raw = request.query_params.get('since')
        since = None
        if since_raw:
            since = parse_datetime(since_raw)
            if since is None:
                parsed_date = parse_date(since_raw)
                if parsed_date is not None:
                    since = timezone.datetime.combine(parsed_date, timezone.datetime.min.time())
            if since is None:
                return Response(
                    {'detail': 'Invalid since value. Use ISO 8601 date or datetime.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            payload = build_delta_export_payload(category=category, since=since)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(payload)


class ETLDeltaImportView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='Import ETL delta for a category',
        request=ETLDeltaImportRequestSerializer,
        responses={
            200: ETLDeltaImportResponseSerializer,
            400: ETLErrorSerializer,
            404: ETLErrorSerializer,
            409: ETLConflictResponseSerializer,
        },
        examples=[ETL_SHARED_CONFLICT_EXAMPLE],
    )
    def post(self, request, category):
        try:
            payload = import_delta_payload(category=category, payload=request.data)
        except ETLImportConflictError as exc:
            return Response(exc.to_payload(), status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            status_code = status.HTTP_404_NOT_FOUND if 'Unsupported' in str(exc) else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=status_code)

        return Response(payload, status=status.HTTP_200_OK)


class ETLManuscriptListView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='List manuscripts available for ETL package export',
        responses={200: ETLManuscriptListResponseSerializer, 401: ETLErrorSerializer},
    )
    def get(self, request):
        return Response(build_manuscript_list_payload())


class ETLManuscriptExportView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='Export one manuscript package',
        responses={200: ETLManuscriptExportResponseSerializer, 404: ETLErrorSerializer},
        examples=[ETL_MANUSCRIPT_EXPORT_EXAMPLE],
    )
    def get(self, request, manuscript_uuid):
        try:
            payload = build_manuscript_export_payload(manuscript_uuid)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(payload)


class ETLManuscriptImportView(ETLAPIView):

    @extend_schema(
        tags=['ETL'],
        summary='Import one manuscript package',
        request=ETLManuscriptImportRequestSerializer,
        responses={200: ETLManuscriptImportResponseSerializer, 400: ETLErrorSerializer},
    )
    def post(self, request):
        try:
            payload = import_manuscript_payload(request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload, status=status.HTTP_200_OK)


class ETLUIAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': 'Authentication required.'}, status=401)
        if not user_can_manage_etl(request.user):
            return JsonResponse({'detail': 'Insufficient permissions for ETL sync.'}, status=403)
        return super().dispatch(request, *args, **kwargs)


class ETLAdminSyncView(View):
    template_name = 'admin/etl_sync.html'

    def get(self, request, *args, **kwargs):
        if not user_can_manage_etl(request.user):
            raise PermissionDenied('Insufficient permissions for ETL sync.')

        context = {
            **admin.site.each_context(request),
            'title': 'ETL sync',
        }
        return TemplateResponse(request, self.template_name, context)


@method_decorator(csrf_exempt, name='dispatch')
class ETLUIOverviewView(ETLUIAccessMixin, View):
    def get(self, request, *args, **kwargs):
        peers = []
        for peer in get_etl_peer_configs():
            peer_info = {
                'id': peer['id'],
                'label': peer['label'],
                'url': peer['url'],
            }
            try:
                peer_info['status'] = fetch_remote_etl_json(
                    peer['url'],
                    '/api/etl/status/',
                    api_token=peer.get('api_token'),
                )
                peer_info['reachable'] = True
                peer_info['error'] = None
            except ValueError as exc:
                peer_info['status'] = None
                peer_info['reachable'] = False
                peer_info['error'] = str(exc)
            peers.append(peer_info)

        return JsonResponse(
            {
                'local': build_status_payload(),
                'peers': peers,
            }
        )


@method_decorator(csrf_exempt, name='dispatch')
class ETLUIPeerManuscriptsView(ETLUIAccessMixin, View):
    def get(self, request, *args, **kwargs):
        peer_id = request.GET.get('peer')
        if not peer_id:
            return JsonResponse({'detail': 'Missing peer parameter.'}, status=400)

        try:
            peer = resolve_etl_peer(peer_id)
            payload = fetch_remote_etl_json(
                peer['url'],
                '/api/etl/manuscripts/list/',
                api_token=peer.get('api_token'),
            )
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        return JsonResponse(
            {
                'peer': {
                    'id': peer['id'],
                    'label': peer['label'],
                    'url': peer['url'],
                },
                'payload': payload,
            }
        )


@method_decorator(csrf_exempt, name='dispatch')
class ETLUIPullCategoryView(ETLUIAccessMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            body = _load_json_body(request)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        peer_id = body.get('peer')
        category = body.get('category')
        since = body.get('since') or None
        force_remote_uuids = body.get('force_remote_uuids') or []
        keep_local_uuids = body.get('keep_local_uuids') or []
        async_mode = body.get('async', True)  # Default to async for UI

        if not peer_id or not category:
            return JsonResponse({'detail': 'Request body must include peer and category.'}, status=400)

        try:
            peer = resolve_etl_peer(peer_id)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        if async_mode:
            try:
                task = pull_category_task.delay(
                    peer['url'],
                    category,
                    since=since,
                    force_remote_uuids=force_remote_uuids,
                    keep_local_uuids=keep_local_uuids,
                )
            except Exception as exc:
                async_mode = False
                async_error = str(exc)
            else:
                return JsonResponse({
                    'task_id': task.id,
                    'status': 'queued',
                    'peer': {
                        'id': peer['id'],
                        'label': peer['label'],
                        'url': peer['url'],
                    },
                })

        if not async_mode:
            try:
                result = pull_remote_category(
                    peer['url'],
                    category,
                    since=since,
                    force_remote_uuids=force_remote_uuids,
                    keep_local_uuids=keep_local_uuids,
                )
            except ETLImportConflictError as exc:
                return JsonResponse(exc.to_payload(), status=409)
            except ValueError as exc:
                return JsonResponse({'detail': str(exc)}, status=400)

            return JsonResponse(
                {
                    'peer': {
                        'id': peer['id'],
                        'label': peer['label'],
                        'url': peer['url'],
                    },
                    'async_fallback': True if 'async_error' in locals() else False,
                    'async_error': async_error if 'async_error' in locals() else None,
                    'result': result,
                }
            )


@method_decorator(csrf_exempt, name='dispatch')
class ETLUIPullManuscriptView(ETLUIAccessMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            body = _load_json_body(request)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        peer_id = body.get('peer')
        manuscript_uuid = body.get('manuscript_uuid')
        async_mode = body.get('async', True)  # Default to async for UI

        if not peer_id or not manuscript_uuid:
            return JsonResponse({'detail': 'Request body must include peer and manuscript_uuid.'}, status=400)

        try:
            peer = resolve_etl_peer(peer_id)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        if async_mode:
            try:
                task = pull_manuscript_task.delay(peer['url'], manuscript_uuid)
            except Exception as exc:
                async_mode = False
                async_error = str(exc)
            else:
                return JsonResponse({
                    'task_id': task.id,
                    'status': 'queued',
                    'peer': {
                        'id': peer['id'],
                        'label': peer['label'],
                        'url': peer['url'],
                    },
                })

        if not async_mode:
            try:
                result = pull_remote_manuscript(peer['url'], manuscript_uuid)
            except ValueError as exc:
                return JsonResponse({'detail': str(exc)}, status=400)

            return JsonResponse(
                {
                    'peer': {
                        'id': peer['id'],
                        'label': peer['label'],
                        'url': peer['url'],
                    },
                    'async_fallback': True if 'async_error' in locals() else False,
                    'async_error': async_error if 'async_error' in locals() else None,
                    'result': result,
                }
            )


@method_decorator(csrf_exempt, name='dispatch')
class ETLUIResolveConflictView(ETLUIAccessMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            body = _load_json_body(request)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        peer_id = body.get('peer')
        category = body.get('category')
        since = body.get('since') or None
        force_remote_uuids = body.get('force_remote_uuids') or []
        keep_local_uuids = body.get('keep_local_uuids') or []

        try:
            if not peer_id or not category:
                raise ValueError('Request body must include peer and category.')

            peer = resolve_etl_peer(peer_id)
            result = resolve_shared_conflict(
                peer['url'],
                category,
                body.get('conflict'),
                body.get('resolution'),
                since=since,
                force_remote_uuids=force_remote_uuids,
                keep_local_uuids=keep_local_uuids,
            )
        except ETLImportConflictError as exc:
            return JsonResponse(exc.to_payload(), status=409)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)

        return JsonResponse({'result': result})


@method_decorator(csrf_exempt, name='dispatch')
class ETLUITaskStatusView(ETLUIAccessMixin, View):
    def get(self, request, task_id):
        from celery.result import AsyncResult
        from ecatalogus.celery import app

        try:
            result = AsyncResult(task_id, app=app)
            response_data = {
                'task_id': task_id,
                'status': result.status,
            }

            if result.ready():
                if result.successful():
                    response_data['result'] = result.result
                else:
                    response_data['error'] = str(result.result) if result.result else 'Task failed'
        except Exception as exc:
            response_data = {
                'task_id': task_id,
                'status': 'FAILURE',
                'error': str(exc),
            }

        return JsonResponse(response_data)


def _load_json_body(request):
    if not request.body:
        return {}

    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError('Request body must be valid JSON.') from exc
