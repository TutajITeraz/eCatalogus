"""Public API v1.

Authentication is deliberately boring: a normal eCatalogus username and password
over HTTPS, sent either as a browser session (for anything in-app) or as HTTP
Basic (for machine-to-machine callers such as ritus-indexer). No separate token
store to provision, rotate or leak.

Reads are open to everyone. Writes require an account that is either a
superuser, a member of the ``api_importers`` group, or holds the relevant Django
model permission — see :mod:`indexerapp.api_access`.
"""

from django.conf import settings
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from indexerapp.api_access import ApiV1AnonRateThrottle, EditorWriteOnly, user_can_write_api
from indexerapp.models import Content, Manuscripts

from . import dictionaries as dictionaries_module
from . import schema_examples as examples
from . import serializers as api_serializers
from .authentication import SilentBasicAuthentication
from .licensing import (
    LICENSE_LINK_REL,
    attach_rights,
    collect_contributors,
    get_license,
    license_url,
)
from .export import (
    build_content_summary,
    build_manuscript_package,
    content_queryset,
    object_label,
    serialize_content_row,
)
from .importers import ImportValidationError, create_manuscript, import_content_bulk


V1_TAG = 'Public API v1'

PAGING_PARAMETERS = [
    OpenApiParameter(
        'limit', int,
        description='Page size. Default 100, maximum 2000; larger values are clamped.',
    ),
    OpenApiParameter(
        'offset', int,
        description='Zero-based index of the first record. Use `next_offset` from the previous page.',
    ),
]

AUTH_NOTE = (
    '\n\n**Authentication:** requires an eCatalogus account that is a superuser, a member '
    'of the `api_importers` group, or holds the matching Django permission. Send it as '
    'HTTP Basic over HTTPS (`curl -u user:password …`). A wrong password answers 401; '
    'a valid account without import rights answers 403.'
)

#: Everything ``/api/v1/dictionaries/{slug}/`` understands. Anything else is a
#: typo or a wrong assumption, and answering 200 to it hides both.
DICTIONARY_QUERY_PARAMS = frozenset({
    'search', 'since', 'uuids', 'legacy_ids', 'fields', 'limit', 'offset', 'format',
})

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 2000


def _paging(request, default=DEFAULT_PAGE_SIZE, maximum=MAX_PAGE_SIZE):
    try:
        limit = int(request.query_params.get('limit', default))
    except (TypeError, ValueError):
        limit = default
    try:
        offset = int(request.query_params.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    return min(max(limit, 1), maximum), max(offset, 0)


def _get_manuscript_or_404(manuscript_uuid):
    manuscript = Manuscripts.objects.filter(uuid=manuscript_uuid).first()
    if manuscript is None:
        raise _NotFound(f'No manuscript with uuid {manuscript_uuid}.')
    return manuscript


class _NotFound(Exception):
    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


class V1View(APIView):
    """Shared behaviour: uniform 404s and browser-friendly authentication.

    Session covers same-origin calls from eCatalogus' own pages; silent Basic
    covers a partner site's JavaScript, where the user supplies their eCatalogus
    credentials at upload time.

    Basic is listed first deliberately. DRF takes the challenge header for a
    failed authentication from the *first* authenticator, and SessionAuthentication
    supplies none — which downgrades a wrong password from 401 to 403 and makes
    "you typed the password wrong" indistinguishable from "your account may not
    import". Basic (without a header, or with one) still falls through to session
    authentication.
    """

    authentication_classes = [SilentBasicAuthentication, SessionAuthentication]
    throttle_classes = [ApiV1AnonRateThrottle]
    # JSON only, whatever the Accept header says. The browsable API renderer in
    # the project defaults needs rest_framework's templates, which are not
    # installed — a link opened in a browser answered 500 instead of the data.
    renderer_classes = [JSONRenderer]

    def handle_exception(self, exc):
        if isinstance(exc, _NotFound):
            return Response({'detail': exc.detail}, status=status.HTTP_404_NOT_FOUND)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        """Advertise the data licence on every response, including errors.

        Payloads get saved to files and headers get lost, so the licence is also
        repeated inside the body — but the header is what survives proxying and
        makes the terms discoverable without parsing anything.
        """
        response = super().finalize_response(request, response, *args, **kwargs)

        url = license_url()
        if url:
            response['Link'] = f'<{url}>; rel="{LICENSE_LINK_REL}"'

        return response


class WriteView(V1View):
    """Write endpoints: authorised accounts only, never rate limited.

    Bulk imports are the whole point of the integration, so throttling them
    would defeat the purpose. Only authenticated, explicitly authorised callers
    can get this far.
    """

    permission_classes = [EditorWriteOnly]
    throttle_classes = []


class RootView(V1View):

    @extend_schema(
        tags=[V1_TAG],
        summary='API v1 discovery document',
        operation_id='v1_root',
        description=(
            'Entry point for a client exploring the API: the instance name, a link to this '
            'documentation, URL templates for every endpoint and the licence the data is '
            'published under. Public, no authentication.'
        ),
        responses={200: api_serializers.RootSerializer},
    )
    def get(self, request):
        # Resolve the host once and append the paths verbatim: build_absolute_uri
        # percent-encodes the braces, which turns the {uuid} placeholder of a
        # URL template into %7Buuid%7D.
        origin = request.build_absolute_uri('/').rstrip('/')

        def url(path):
            return origin + path

        return Response({
            'api_version': 'v1',
            'site_name': getattr(settings, 'SITE_NAME', ''),
            'documentation': url('/api/schema/swagger/'),
            'endpoints': {
                'whoami': url('/api/v1/whoami/'),
                'manuscripts': url('/api/v1/manuscripts/'),
                'manuscript_package': url('/api/v1/manuscripts/{uuid}/package/'),
                'manuscript_content': url('/api/v1/manuscripts/{uuid}/content/'),
                'manuscript_content_summary': url('/api/v1/manuscripts/{uuid}/content/summary/'),
                'manuscript_content_bulk': url('/api/v1/manuscripts/{uuid}/content/bulk/'),
                'dictionaries': url('/api/v1/dictionaries/'),
            },
            'rights': get_license(),
        })


class WhoAmIView(V1View):
    """Credential check for the partner site's login form.

    Lets the calling page tell the user "you are signed in as X and may import"
    *before* it spends time generating a payload — and lets it distinguish a
    typo in the password from an account that simply lacks import rights.
    """

    # Never throttled: this is the first call a legitimate integration makes.
    throttle_classes = []

    @extend_schema(
        tags=[V1_TAG],
        summary='Confirm who the supplied credentials belong to',
        operation_id='v1_whoami',
        description=(
            'Returns the identity behind the request. Call it as soon as a user submits '
            'their eCatalogus login, before generating or uploading anything.\n\n'
            '| Result | Meaning |\n'
            '|---|---|\n'
            '| `401` | Wrong username or password. |\n'
            '| `200`, `can_import: false` | Credentials fine, but the account may not import. '
            'An administrator must add it to the `api_importers` group. |\n'
            '| `200`, `can_import: true` | Ready to upload. |\n\n'
            'Without credentials it answers 200 with `authenticated: false`. A failed login '
            'answers 401 with `WWW-Authenticate: xBasic`, a scheme browsers do not recognise, '
            'so a page calling this from JavaScript never gets the browser\'s own password '
            'pop-up on top of its form. Never throttled.'
        ),
        examples=examples.WHOAMI_EXAMPLES,
        responses={200: api_serializers.WhoAmISerializer, 401: api_serializers.ErrorSerializer},
    )
    def get(self, request):
        user = request.user
        authenticated = bool(getattr(user, 'is_authenticated', False))

        return Response({
            'api_version': 'v1',
            'site_name': getattr(settings, 'SITE_NAME', ''),
            'authenticated': authenticated,
            'username': user.get_username() if authenticated else None,
            'display_name': (user.get_full_name() or user.get_username()) if authenticated else None,
            'can_import': user_can_write_api(user, ('add_content',)),
        })


class ManuscriptListView(V1View):
    required_permissions = ('add_manuscripts',)

    @extend_schema(
        tags=[V1_TAG],
        summary='List manuscripts',
        operation_id='v1_manuscripts_list',
        description=(
            'Manuscripts catalogued on this instance, ordered by name, with the number of '
            'content rows each one has. Public, no authentication.\n\n'
            'Filters combine with AND. `search` is a case-insensitive substring match; '
            '`foreign_id` is exact, which makes it the way to look up a manuscript by the '
            'identifier your own system gave it.'
        ),
        parameters=[
            OpenApiParameter(
                'search', str,
                description='Case-insensitive substring of the name, shelf mark, RISM id or foreign id.',
            ),
            OpenApiParameter('foreign_id', str, description='Exact match on the calling system\'s identifier.'),
            *PAGING_PARAMETERS,
        ],
        examples=examples.MANUSCRIPT_LIST_EXAMPLES,
        responses={200: api_serializers.ManuscriptListSerializer},
    )
    def get(self, request):
        queryset = Manuscripts.objects.select_related(
            'contemporary_repository_place_uuid', 'dating_uuid',
        ).order_by('name')

        search = request.query_params.get('search')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(shelf_mark__icontains=search)
                | Q(rism_id__icontains=search)
                | Q(foreign_id__icontains=search)
            )

        foreign_id = request.query_params.get('foreign_id')
        if foreign_id:
            queryset = queryset.filter(foreign_id=foreign_id)

        total = queryset.count()
        limit, offset = _paging(request)

        results = []
        for manuscript in queryset[offset:offset + limit]:
            place = manuscript.contemporary_repository_place_uuid
            dating = manuscript.dating_uuid
            results.append({
                'uuid': str(manuscript.uuid) if manuscript.uuid else None,
                'name': manuscript.name,
                'rism_id': manuscript.rism_id,
                'foreign_id': manuscript.foreign_id,
                'shelf_mark': manuscript.shelf_mark,
                'contemporary_repository_place_label': object_label(place) if place else None,
                'dating_label': object_label(dating) if dating else None,
                'content_count': Content.objects.filter(manuscript_uuid=manuscript).count(),
                'entry_date': manuscript.entry_date.isoformat() if manuscript.entry_date else None,
            })

        payload = {
            'api_version': 'v1',
            'site_name': getattr(settings, 'SITE_NAME', ''),
            'count': total,
            'limit': limit,
            'offset': offset,
            'next_offset': offset + limit if offset + limit < total else None,
            'results': results,
        }
        attach_rights(payload, request=request)
        return Response(payload)

    @extend_schema(
        tags=[V1_TAG],
        summary='Create a manuscript',
        operation_id='v1_manuscripts_create',
        description=(
            'Creates one manuscript and returns its `uuid`, which every later call uses. '
            'Only `name` is required.\n\n'
            'Relation fields (`contemporary_repository_place`, `dating`, `place_of_origin`, '
            '`main_script`, `binding_date`, `binding_place`) accept either a UUID or the '
            'dictionary entry\'s name, matched case-insensitively. Unknown names are an '
            'error: the API never creates dictionary entries. Read the vocabularies under '
            '`/api/v1/dictionaries/` to validate values before sending.\n\n'
            'Unrecognised keys are rejected. Add `?strict=false` to ignore them instead. '
            'Every problem is reported at once, and nothing is created if there is any.'
            + AUTH_NOTE
        ),
        parameters=[
            OpenApiParameter(
                'strict', bool,
                description='Reject unrecognised keys (default true). `false` ignores them.',
            ),
        ],
        request=api_serializers.ManuscriptCreateSerializer,
        examples=examples.MANUSCRIPT_CREATE_EXAMPLES,
        responses={
            201: api_serializers.ManuscriptCreatedSerializer,
            400: api_serializers.ValidationFailureSerializer,
            401: api_serializers.ErrorSerializer,
            403: api_serializers.ErrorSerializer,
        },
    )
    def post(self, request):
        # Authorisation is enforced here rather than on the class so that GET
        # stays public while POST does not.
        permission = EditorWriteOnly()
        if not permission.has_permission(request, self):
            return Response({'detail': permission.message}, status=status.HTTP_403_FORBIDDEN)

        strict = str(request.query_params.get('strict', 'true')).lower() != 'false'

        try:
            manuscript = create_manuscript(request.data, strict_keys=strict)
        except ImportValidationError as exc:
            return Response(
                {'detail': exc.detail, 'errors': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'uuid': str(manuscript.uuid) if manuscript.uuid else None,
                'name': manuscript.name,
                'foreign_id': manuscript.foreign_id,
                'content_count': 0,
                'entry_date': manuscript.entry_date.isoformat() if manuscript.entry_date else None,
            },
            status=status.HTTP_201_CREATED,
        )


class ManuscriptPackageView(V1View):

    @extend_schema(
        tags=[V1_TAG],
        summary='Export one manuscript in full',
        operation_id='v1_manuscript_package',
        description=(
            'Every record attached to the manuscript — codicology, layouts, quires, '
            'binding, decoration, origins, provenance, hands, watermarks, content. '
            'This is the complete data behind the manuscript tab, and a superset of '
            'the TEI XML export.\n\n'
            'By default each foreign key is accompanied by a `*_label` key holding the '
            'human-readable name, so the package can be read without downloading the '
            'dictionaries. Pass `labels=false` for the raw UUID-only form.\n\n'
            'The response is one block per model (`models[]`), each holding the records of '
            'that model that belong to the manuscript. Instance-local numeric ids are left '
            'out: records reference each other by UUID only.\n\n'
            'Images are not embedded. `media_files` lists each attached image with its '
            'path, size in bytes and an absolute URL, so you download only the images '
            'you need, straight from the web server.\n\n'
            'Public, no authentication. `rights.contributors` credits every person named '
            'by the records in the package.'
        ),
        parameters=[
            OpenApiParameter('labels', bool, description='Include *_label keys. Default true.'),
        ],
        examples=examples.PACKAGE_EXAMPLES,
        responses={200: api_serializers.ManuscriptPackageSerializer, 404: api_serializers.ErrorSerializer},
    )
    def get(self, request, manuscript_uuid):
        with_labels = str(request.query_params.get('labels', 'true')).lower() != 'false'
        try:
            payload = build_manuscript_package(
                manuscript_uuid, with_labels=with_labels, build_uri=request.build_absolute_uri,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        attach_rights(
            payload,
            request=request,
            title=payload.get('manuscript_name'),
            contributors=collect_contributors(payload),
        )
        return Response(payload)


class ManuscriptContentView(V1View):

    @extend_schema(
        tags=[V1_TAG],
        summary='List a manuscript\'s content',
        operation_id='v1_manuscript_content_list',
        description=(
            'Flat content rows — one per liturgical item — ordered by `sequence_in_ms`. '
            'They use exactly the vocabulary the bulk import accepts, so the output of '
            'this endpoint can be posted back unchanged.\n\n'
            'Each relation appears as a UUID (e.g. `function_id`) plus a readable '
            '`*_label` (e.g. `function_label: "Collecta"`), so rows can be displayed '
            'without downloading any dictionary. Page through with `limit`/`offset` until '
            '`next_offset` is null. Public, no authentication.'
        ),
        parameters=PAGING_PARAMETERS,
        examples=examples.CONTENT_LIST_EXAMPLES,
        responses={200: api_serializers.ContentListSerializer, 404: api_serializers.ErrorSerializer},
    )
    def get(self, request, manuscript_uuid):
        manuscript = _get_manuscript_or_404(manuscript_uuid)
        queryset = content_queryset(manuscript)
        total = queryset.count()
        limit, offset = _paging(request)

        payload = {
            'api_version': 'v1',
            'manuscript_uuid': str(manuscript.uuid) if manuscript.uuid else None,
            'manuscript_name': manuscript.name,
            'count': total,
            'limit': limit,
            'offset': offset,
            'next_offset': offset + limit if offset + limit < total else None,
            'results': [serialize_content_row(row) for row in queryset[offset:offset + limit]],
        }
        attach_rights(payload, request=request, title=manuscript.name)
        return Response(payload)


class ManuscriptContentSummaryView(V1View):

    @extend_schema(
        tags=[V1_TAG],
        summary='Check whether a manuscript already has content',
        operation_id='v1_manuscript_content_summary',
        description=(
            'Cheap probe to call before uploading, so a retry or a re-run does not create '
            'duplicates. If `has_content` is true, either stop, or upload with '
            '`mode: "replace"` to overwrite what is there. Public, no authentication.'
        ),
        examples=examples.CONTENT_SUMMARY_EXAMPLES,
        responses={200: api_serializers.ContentSummarySerializer, 404: api_serializers.ErrorSerializer},
    )
    def get(self, request, manuscript_uuid):
        manuscript = _get_manuscript_or_404(manuscript_uuid)
        payload = build_content_summary(manuscript)
        attach_rights(payload, request=request, title=manuscript.name)
        return Response(payload)


class ManuscriptContentBulkView(WriteView):
    required_permissions = ('add_content',)

    @extend_schema(
        tags=[V1_TAG],
        summary='Bulk import content rows',
        operation_id='v1_manuscript_content_bulk',
        description=(
            'Imports many content rows in one request — there is no row limit and no '
            'rate limit. The entire payload is validated first: if any row is bad, '
            'nothing is written and every problem is reported with its row index, '
            'field and value.\n\n'
            'Dictionary values (rubric, liturgical genre, function, …) may be given as '
            'a UUID or as the entry\'s name. Names that do not exist are an error — '
            'the API never invents dictionary entries.\n\n'
            'Send `dry_run: true` first to validate a batch without writing.\n\n'
            'The write is one transaction: with `mode: "replace"` the old rows are deleted '
            'and the new ones written together, or not at all. Rows without '
            '`sequence_in_ms` are numbered after the highest existing one. Allow roughly one '
            'second per hundred rows and set a generous client timeout.\n\n'
            '**Plain fields:** `sequence_in_ms`, `rubric_sequence_in_the_MS`, '
            '`digital_page_number` (whole numbers); `proper_texts` (boolean); '
            '`rubric_name_from_ms`, `subrubric_name_from_ms`, `formula_text_from_ms`, '
            '`where_in_ms_from`, `where_in_ms_to`, `original_or_added` (`ORIGINAL` / '
            '`ADDED`), `biblical_reference`, `reference_to_other_items`, '
            '`similarity_by_user`, `edition_subindex`, `comments` (text).\n\n'
            '**Relations** — a UUID, or a name matched case-insensitively against:\n\n'
            '| Key | Dictionary | Name column |\n'
            '|---|---|---|\n'
            '| `rubric_id` | rite-names | `name` |\n'
            '| `liturgical_genre_id` | liturgical-genres | `title` |\n'
            '| `section_id`, `subsection_id` | sections | `name` |\n'
            '| `function_id`, `subfunction_id` | content-functions | `name` |\n'
            '| `layer`, `mass_hour`, `genre`, `season_month`, `week`, `day` | same-named | '
            '`short_name`, then `name` |\n'
            '| `text_standarization` | text-standarization | `standard_incipit` |\n'
            '| `contributor_id` | contributors | `initials` |\n'
            '| `formula_id` | formulas | UUID only — look it up by `co_no` first |\n'
            '| `quire_id` | the manuscript\'s quires | UUID only |\n'
            '| `music_notation_id` | music-notation-names | `name`, resolved to this '
            'manuscript\'s own notation record |\n'
            '| `edition_index` | edition content | `"<bibliography shortname> c.<sequence>"` |\n\n'
            'Keys returned by the export but not written (`uuid`, `manuscript_uuid`, '
            '`entry_date`, `*_label`) are accepted and ignored.'
            + AUTH_NOTE
        ),
        request=api_serializers.ContentBulkRequestSerializer,
        examples=examples.CONTENT_BULK_EXAMPLES,
        responses={
            200: api_serializers.ContentBulkResponseSerializer,
            400: api_serializers.ValidationFailureSerializer,
            401: api_serializers.ErrorSerializer,
            403: api_serializers.ErrorSerializer,
            404: api_serializers.ErrorSerializer,
        },
    )
    def post(self, request, manuscript_uuid):
        manuscript = _get_manuscript_or_404(manuscript_uuid)

        payload = request.data
        if isinstance(payload, list):
            # Accept a bare list, matching the legacy /content_import/ shape.
            payload = {'items': payload}

        if not isinstance(payload, dict):
            return Response(
                {'detail': 'Expected a JSON object with an "items" list, or a bare JSON list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            report = import_content_bulk(
                manuscript,
                payload.get('items'),
                mode=payload.get('mode', 'append'),
                dry_run=bool(payload.get('dry_run', False)),
                strict_keys=bool(payload.get('strict', True)),
            )
        except ImportValidationError as exc:
            return Response(
                {'detail': exc.detail, 'errors': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(report, status=status.HTTP_200_OK)


class DictionaryListView(V1View):

    @extend_schema(
        tags=[V1_TAG],
        summary='List the published controlled vocabularies',
        operation_id='v1_dictionaries_list',
        description=(
            'Every controlled vocabulary this instance publishes, with its slug, entry '
            'count and URL. Vocabularies are curated in eCatalogus and replicated to the '
            'other instances, so their UUIDs are the same everywhere and safe to store. '
            'Read-only and public.'
        ),
        examples=examples.DICTIONARY_LIST_EXAMPLES,
        responses={200: api_serializers.DictionaryListSerializer},
    )
    def get(self, request):
        payload = dictionaries_module.list_dictionaries(request.build_absolute_uri)
        attach_rights(payload, request=request)
        return Response(payload)


class DictionaryDetailView(V1View):

    @extend_schema(
        tags=[V1_TAG],
        summary='Read one controlled vocabulary',
        operation_id='v1_dictionary_detail',
        description=(
            'Entries of one vocabulary, ordered by creation. Default page size is 200, '
            'maximum 1000. Selecting entries with `uuids` or `legacy_ids` returns all of '
            'them in one page (up to 1000).\n\n'
            'Typical uses:\n'
            '* **Validate names before an import** — `?search=Collecta&fields=name`.\n'
            '* **Mirror a vocabulary** — page through with `limit=1000`, then keep it '
            'current with `?since=<timestamp of your last sync>`.\n'
            '* **Resolve ids you already hold** — `?uuids=…` or, for numbering from the '
            'legacy database, `?legacy_ids=…`.\n\n'
            'Unknown query parameters are rejected with 400 rather than ignored, so a typo '
            'cannot silently return the whole vocabulary. Public, no authentication.'
        ),
        examples=examples.DICTIONARY_PAGE_EXAMPLES,
        parameters=[
            OpenApiParameter(
                'slug', str, OpenApiParameter.PATH,
                description='Vocabulary slug from `/api/v1/dictionaries/`, e.g. `rite-names`.',
            ),
            OpenApiParameter(
                'search', str,
                description=(
                    'Case-insensitive substring match on the vocabulary\'s name columns '
                    '(e.g. `co_no` and `text` for formulas, `name` and '
                    '`english_translation` for rite-names).'
                ),
            ),
            OpenApiParameter(
                'since', str,
                description=(
                    'ISO-8601 timestamp, e.g. `2026-09-01T00:00:00Z`; only entries changed '
                    'since then. Ignored by vocabularies that have no `entry_date` column.'
                ),
            ),
            OpenApiParameter(
                'uuids', str,
                description=(
                    'Comma-separated UUIDs; returns only those entries. '
                    f'At most {dictionaries_module.MAX_SELECTED_KEYS} per request.'
                ),
            ),
            OpenApiParameter(
                'legacy_ids', str,
                description=(
                    'Comma-separated ids from the legacy database, for systems that still '
                    'hold that numbering. Each record gains a "legacy_id" key, and ids with '
                    'no entry are listed in "unresolved_legacy_ids". Never the local "id" '
                    'column, which differs per instance.'
                ),
            ),
            OpenApiParameter(
                'fields', str,
                description='Comma-separated columns to return. "uuid" is always included.',
            ),
            OpenApiParameter('limit', int, description=f'Max {dictionaries_module.MAX_PAGE_SIZE}.'),
            OpenApiParameter('offset', int),
        ],
        responses={
            200: api_serializers.DictionaryPageSerializer,
            400: api_serializers.ErrorSerializer,
            404: api_serializers.ErrorSerializer,
        },
    )
    def get(self, request, slug):
        unknown = sorted(set(request.query_params) - DICTIONARY_QUERY_PARAMS)
        if unknown:
            return Response(
                {
                    'detail': (
                        f'Unknown query parameter(s): {", ".join(unknown)}. '
                        f'This endpoint accepts: {", ".join(sorted(DICTIONARY_QUERY_PARAMS))}.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        since_raw = request.query_params.get('since')
        since = parse_datetime(since_raw) if since_raw else None
        if since_raw and since is None:
            return Response(
                {'detail': f'Could not parse "since" value "{since_raw}" as an ISO-8601 timestamp.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uuids_raw = request.query_params.get('uuids')
        legacy_ids_raw = request.query_params.get('legacy_ids')
        try:
            uuids = dictionaries_module.parse_uuid_list(uuids_raw) if uuids_raw is not None else None
            legacy_ids = (
                dictionaries_module.parse_legacy_id_list(legacy_ids_raw)
                if legacy_ids_raw is not None else None
            )
        except dictionaries_module.DictionaryQueryError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Naming entries explicitly is a request for all of them, not for the
        # first page of them — a caller resolving 400 formulas wants 400 back.
        default_page_size = (
            dictionaries_module.MAX_PAGE_SIZE
            if (uuids is not None or legacy_ids is not None)
            else dictionaries_module.DEFAULT_PAGE_SIZE
        )
        limit, offset = _paging(
            request,
            default=default_page_size,
            maximum=dictionaries_module.MAX_PAGE_SIZE,
        )

        try:
            payload = dictionaries_module.build_dictionary_page(
                slug, search=request.query_params.get('search'),
                since=since, limit=limit, offset=offset,
                uuids=uuids, legacy_ids=legacy_ids,
                fields=request.query_params.get('fields'),
            )
        except LookupError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)

        attach_rights(payload, request=request)
        return Response(payload)
