"""Serializers used purely to describe the v1 API in the OpenAPI schema.

The endpoints hand-build their payloads — these classes exist so drf-spectacular
can document request and response shapes for the integration guide.
"""

from rest_framework import serializers


API_VERSION_HELP = 'Always "v1" for this API.'
SITE_NAME_HELP = (
    'Name of the instance that answered, e.g. "eCatalogus", "MPL Limbo", "Canon Missae". '
    'Every instance runs the same API over its own data.'
)
COUNT_HELP = 'Total number of matching records, across all pages.'
LIMIT_HELP = 'Page size actually applied (after clamping to the maximum).'
OFFSET_HELP = 'Zero-based index of the first record on this page.'
NEXT_OFFSET_HELP = (
    'Pass this as `?offset=` to fetch the next page; `null` when this is the last page.'
)


class RightsSerializer(serializers.Serializer):
    """Licence and attribution block attached to every read response."""

    license = serializers.CharField(help_text='SPDX identifier of the data licence, e.g. "CC-BY-NC-4.0".')
    license_name = serializers.CharField(help_text='Human-readable licence name.')
    license_url = serializers.URLField(help_text='Canonical URL of the licence text.')
    copyright = serializers.CharField(help_text='Copyright notice.')
    rights_holder = serializers.CharField(help_text='Institution holding the rights to the data.')
    rights_holder_url = serializers.URLField()
    required_statement = serializers.CharField(
        help_text='Attribution that the licence obliges a reuser to reproduce.',
    )
    attribution = serializers.CharField(
        help_text='Ready-made attribution line naming the record and its contributors.',
    )
    accessed = serializers.DateTimeField(help_text='When this response was generated.')
    source = serializers.URLField(help_text='The exact URL that produced this response.')
    recommended_citation = serializers.CharField(help_text='Citation string, ready to paste.')
    contributors = serializers.ListField(
        child=serializers.JSONField(), required=False,
        help_text=(
            'Only on the manuscript package: the people credited by the records in the '
            'export (uuid, name, initials, affiliation, url).'
        ),
    )


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text='Human-readable explanation of what went wrong.')


class RowErrorSerializer(serializers.Serializer):
    row = serializers.IntegerField(
        allow_null=True,
        help_text='Zero-based index in the submitted `items` list (always 0 for a manuscript).',
    )
    field = serializers.CharField(allow_null=True, help_text='The offending key, or null for a whole-row problem.')
    value = serializers.JSONField(allow_null=True, help_text='The value that was rejected, echoed back verbatim.')
    error = serializers.ChoiceField(
        choices=['unknown_field', 'invalid_value', 'invalid_row', 'not_found', 'required', 'too_many_errors'],
        help_text=(
            'Machine-readable category:\n'
            '* `unknown_field` — key not recognised (only with `strict: true`);\n'
            '* `invalid_value` — wrong type, e.g. text where a whole number is expected;\n'
            '* `invalid_row` — the item is not a JSON object;\n'
            '* `not_found` — no dictionary entry matches the given UUID or name;\n'
            '* `required` — a mandatory field is missing or blank;\n'
            '* `too_many_errors` — reporting stopped after 200 problems.'
        ),
    )
    detail = serializers.CharField(help_text='Human-readable explanation, safe to show to an end user.')


class ValidationFailureSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text='Summary, e.g. "2 problem(s) found; nothing was imported."')
    errors = RowErrorSerializer(many=True, help_text='Every problem found, not just the first.')


class ManuscriptListItemSerializer(serializers.Serializer):
    uuid = serializers.UUIDField(help_text='Stable identifier. Use it in every other manuscript URL.')
    name = serializers.CharField(help_text='Display name, e.g. "Sacramentarium Tinecense".')
    rism_id = serializers.CharField(allow_null=True, required=False, help_text='RISM siglum, e.g. "PL-Wn BOZ 8".')
    foreign_id = serializers.CharField(
        allow_null=True, required=False,
        help_text='Identifier assigned by an external system (e.g. ritus-indexer).',
    )
    shelf_mark = serializers.CharField(allow_null=True, required=False)
    contemporary_repository_place_label = serializers.CharField(
        allow_null=True, required=False, help_text='Name of the library holding the manuscript today.',
    )
    dating_label = serializers.CharField(allow_null=True, required=False, help_text='Dating, e.g. "XI med".')
    content_count = serializers.IntegerField(help_text='Number of content rows (liturgical items) catalogued.')
    entry_date = serializers.DateTimeField(allow_null=True, required=False, help_text='Last modification time.')


class ManuscriptListSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    site_name = serializers.CharField(help_text=SITE_NAME_HELP)
    count = serializers.IntegerField(help_text=COUNT_HELP)
    limit = serializers.IntegerField(help_text=LIMIT_HELP)
    offset = serializers.IntegerField(help_text=OFFSET_HELP)
    next_offset = serializers.IntegerField(allow_null=True, help_text=NEXT_OFFSET_HELP)
    results = ManuscriptListItemSerializer(many=True)
    rights = RightsSerializer()


class ManuscriptCreateSerializer(serializers.Serializer):
    """Flat manuscript description. Relations accept a UUID or a dictionary name.

    Only the most common fields are listed here. The endpoint also accepts
    usuarium_shelfmark, liturgical_genre_comment, dating_comment,
    place_of_origin_comment, how_many_columns_mostly, lines_per_page_usually,
    how_many_quires, quires_comment, foliation_or_pagination, decorated,
    decoration_comments, music_notation, music_notation_comments, form_of_an_item,
    links, additional_url, pdf_url, connected_ms, where_in_connected_ms and
    display_as_main.
    """

    name = serializers.CharField(help_text='Required. Display name of the manuscript.')
    rism_id = serializers.CharField(required=False, allow_null=True, help_text='RISM siglum, e.g. "PL-Kk 12".')
    foreign_id = serializers.CharField(
        required=False, allow_null=True,
        help_text=(
            'Identifier of this manuscript in the calling system. Lets you find it again '
            'with `GET /api/v1/manuscripts/?foreign_id=…` without keeping a mapping table.'
        ),
    )
    shelf_mark = serializers.CharField(required=False, allow_null=True)
    common_name = serializers.CharField(required=False, allow_null=True)
    contemporary_repository_place = serializers.CharField(
        required=False, allow_null=True,
        help_text=(
            'Where the manuscript is kept today. Places UUID, or the repository name in the '
            'local language or in English (dictionary `places`).'
        ),
    )
    dating = serializers.CharField(
        required=False, allow_null=True,
        help_text='TimeReference UUID or `time_description`, e.g. "XIV" (dictionary `time-reference`).',
    )
    place_of_origin = serializers.CharField(
        required=False, allow_null=True,
        help_text='Places UUID or repository name (dictionary `places`).',
    )
    main_script = serializers.CharField(
        required=False, allow_null=True,
        help_text='ScriptNames UUID or name (dictionary `script-names`).',
    )
    binding_date = serializers.CharField(
        required=False, allow_null=True, help_text='TimeReference UUID or `time_description`.',
    )
    binding_place = serializers.CharField(
        required=False, allow_null=True, help_text='Places UUID or repository name.',
    )
    general_comment = serializers.CharField(required=False, allow_null=True)
    iiif_manifest_url = serializers.CharField(required=False, allow_null=True, help_text='IIIF Presentation manifest URL.')


class ManuscriptCreatedSerializer(serializers.Serializer):
    uuid = serializers.UUIDField(help_text='Keep this — every later call about the manuscript uses it.')
    name = serializers.CharField()
    foreign_id = serializers.CharField(allow_null=True)
    content_count = serializers.IntegerField(help_text='Always 0 for a newly created manuscript.')
    entry_date = serializers.DateTimeField(allow_null=True)


class ContentSummarySerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    site_name = serializers.CharField(help_text=SITE_NAME_HELP)
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    content_count = serializers.IntegerField(help_text='Number of content rows attached to the manuscript.')
    has_content = serializers.BooleanField(help_text='Shorthand for `content_count > 0`.')
    sequence_in_ms_min = serializers.IntegerField(allow_null=True, help_text='Lowest `sequence_in_ms`, or null.')
    sequence_in_ms_max = serializers.IntegerField(
        allow_null=True,
        help_text='Highest `sequence_in_ms`. An append without explicit sequences continues after it.',
    )
    last_modified = serializers.DateTimeField(allow_null=True, help_text='Newest `entry_date` among the rows.')
    rights = RightsSerializer()


class ContentBulkRequestSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.JSONField(),
        help_text=(
            'Content rows, one object per liturgical item. Accepted keys are exactly the keys '
            'returned by `GET /api/v1/manuscripts/{uuid}/content/`, so an export can be posted '
            'back unchanged. A bare JSON list is also accepted as the whole request body.'
        ),
    )
    mode = serializers.ChoiceField(
        choices=['append', 'replace'], default='append', required=False,
        help_text=(
            '`append` (default) only adds rows. `replace` deletes all of the manuscript\'s '
            'existing content first, in the same transaction — use it to re-upload after corrections.'
        ),
    )
    dry_run = serializers.BooleanField(
        default=False, required=False,
        help_text='Validate the whole payload and report every problem without writing anything.',
    )
    strict = serializers.BooleanField(
        default=True, required=False,
        help_text='Reject unrecognised field names (default). Set false to silently ignore them.',
    )


class ContentBulkResponseSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    site_name = serializers.CharField(help_text=SITE_NAME_HELP)
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    mode = serializers.CharField(help_text='The mode that was applied.')
    dry_run = serializers.BooleanField(help_text='True when nothing was written.')
    detail = serializers.CharField(required=False, help_text='Present on a successful dry run.')
    received = serializers.IntegerField(help_text='Number of items in the request.')
    created = serializers.IntegerField(help_text='Rows written (0 on a dry run).')
    deleted = serializers.IntegerField(help_text='Rows removed by `mode: replace`.')
    created_uuids = serializers.ListField(
        child=serializers.UUIDField(), required=False,
        help_text='UUIDs of the new rows, in the order the items were sent. Absent on a dry run.',
    )
    errors = RowErrorSerializer(many=True, help_text='Always empty on success.')


class ContentListSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    count = serializers.IntegerField(help_text=COUNT_HELP)
    limit = serializers.IntegerField(help_text=LIMIT_HELP)
    offset = serializers.IntegerField(help_text=OFFSET_HELP)
    next_offset = serializers.IntegerField(allow_null=True, help_text=NEXT_OFFSET_HELP)
    results = serializers.ListField(
        child=serializers.JSONField(),
        help_text=(
            'Content rows ordered by `sequence_in_ms`. Every relation appears twice: the '
            'UUID under its own key (e.g. `function_id`) and a readable name under the '
            '`*_label` key (e.g. `function_label`).'
        ),
    )
    rights = RightsSerializer()


class ModelBlockSerializer(serializers.Serializer):
    model = serializers.CharField(help_text='Django model label, e.g. "indexerapp.Codicology".')
    category = serializers.CharField(required=False)
    count = serializers.IntegerField(required=False)
    results = serializers.ListField(
        child=serializers.JSONField(),
        help_text=(
            'Records of that model. Foreign keys end in `_uuid`; with labels on, each is '
            'followed by a `*_label` key holding the readable name.'
        ),
    )


class ManuscriptPackageSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    site_name = serializers.CharField(help_text=SITE_NAME_HELP)
    category = serializers.CharField()
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    model_count = serializers.IntegerField(help_text='Number of blocks in `models`.')
    record_count = serializers.IntegerField(help_text='Total records across all blocks.')
    models = ModelBlockSerializer(many=True, help_text='One block per model that has records for this manuscript.')
    media_files = serializers.ListField(
        child=serializers.JSONField(), required=False,
        help_text=(
            'Image files attached to the records, each as `{path, size, url}`: the path '
            'the records refer to, the size in bytes and an absolute URL to download it '
            'from. The files themselves are never embedded.'
        ),
    )
    rights = RightsSerializer()


class DictionaryListItemSerializer(serializers.Serializer):
    slug = serializers.CharField(help_text='Use in `/api/v1/dictionaries/{slug}/`.')
    model = serializers.CharField(help_text='Underlying model label.')
    verbose_name = serializers.CharField()
    count = serializers.IntegerField(help_text='Number of entries.')
    url = serializers.CharField(required=False, help_text='Absolute URL of the vocabulary.')


class DictionaryListSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    count = serializers.IntegerField(help_text='Number of published vocabularies.')
    results = DictionaryListItemSerializer(many=True)
    rights = RightsSerializer()


class DictionaryPageSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    slug = serializers.CharField()
    model = serializers.CharField()
    count = serializers.IntegerField(help_text=COUNT_HELP)
    limit = serializers.IntegerField(help_text=LIMIT_HELP)
    offset = serializers.IntegerField(help_text=OFFSET_HELP)
    next_offset = serializers.IntegerField(allow_null=True, help_text=NEXT_OFFSET_HELP)
    results = serializers.ListField(
        child=serializers.JSONField(),
        help_text=(
            'Entries ordered by creation. Columns vary per vocabulary; `uuid` is always present. '
            '`rite-names` and `formulas` also publish `id`, which is kept identical on every '
            'instance. Foreign keys come with a `*_label`.'
        ),
    )
    unresolved_legacy_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='Only present when ?legacy_ids= was given: the ids with no entry here.',
    )
    rights = RightsSerializer()


class WhoAmISerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    site_name = serializers.CharField(help_text=SITE_NAME_HELP)
    authenticated = serializers.BooleanField(help_text='False when no credentials were sent.')
    username = serializers.CharField(allow_null=True)
    display_name = serializers.CharField(allow_null=True, help_text='Full name, falling back to the username.')
    can_import = serializers.BooleanField(
        help_text='True when this account may create manuscripts and import content.',
    )


class RootSerializer(serializers.Serializer):
    api_version = serializers.CharField(help_text=API_VERSION_HELP)
    site_name = serializers.CharField(help_text=SITE_NAME_HELP)
    documentation = serializers.CharField(help_text='URL of the interactive Swagger UI.')
    endpoints = serializers.DictField(child=serializers.CharField(), help_text='Endpoint name → URL template.')
    rights = serializers.DictField(help_text='Licence summary (id, name, url, copyright, rights holder).')
