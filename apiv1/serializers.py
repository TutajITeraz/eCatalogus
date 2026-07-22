"""Serializers used purely to describe the v1 API in the OpenAPI schema.

The endpoints hand-build their payloads — these classes exist so drf-spectacular
can document request and response shapes for the integration guide.
"""

from rest_framework import serializers


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RowErrorSerializer(serializers.Serializer):
    row = serializers.IntegerField(allow_null=True, help_text='Zero-based index in the submitted list.')
    field = serializers.CharField(allow_null=True)
    value = serializers.JSONField(allow_null=True)
    error = serializers.ChoiceField(
        choices=['unknown_field', 'invalid_value', 'invalid_row', 'not_found', 'required', 'too_many_errors'],
    )
    detail = serializers.CharField()


class ValidationFailureSerializer(serializers.Serializer):
    detail = serializers.CharField()
    errors = RowErrorSerializer(many=True)


class ManuscriptListItemSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    name = serializers.CharField()
    rism_id = serializers.CharField(allow_null=True, required=False)
    shelf_mark = serializers.CharField(allow_null=True, required=False)
    contemporary_repository_place_label = serializers.CharField(allow_null=True, required=False)
    dating_label = serializers.CharField(allow_null=True, required=False)
    content_count = serializers.IntegerField()
    entry_date = serializers.DateTimeField(allow_null=True, required=False)


class ManuscriptListSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    site_name = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    next_offset = serializers.IntegerField(allow_null=True)
    results = ManuscriptListItemSerializer(many=True)


class ManuscriptCreateSerializer(serializers.Serializer):
    """Flat manuscript description. Relations accept a UUID or a dictionary name."""

    name = serializers.CharField(help_text='Required. Display name of the manuscript.')
    rism_id = serializers.CharField(required=False, allow_null=True)
    foreign_id = serializers.CharField(
        required=False, allow_null=True,
        help_text='Identifier of this manuscript in the calling system.',
    )
    shelf_mark = serializers.CharField(required=False, allow_null=True)
    common_name = serializers.CharField(required=False, allow_null=True)
    contemporary_repository_place = serializers.CharField(
        required=False, allow_null=True,
        help_text='Places UUID or repository name.',
    )
    dating = serializers.CharField(
        required=False, allow_null=True,
        help_text='TimeReference UUID or time_description, e.g. "s. XIV in.".',
    )
    place_of_origin = serializers.CharField(required=False, allow_null=True)
    main_script = serializers.CharField(
        required=False, allow_null=True,
        help_text='ScriptNames UUID or name.',
    )
    binding_date = serializers.CharField(required=False, allow_null=True)
    binding_place = serializers.CharField(required=False, allow_null=True)
    general_comment = serializers.CharField(required=False, allow_null=True)
    iiif_manifest_url = serializers.CharField(required=False, allow_null=True)


class ContentSummarySerializer(serializers.Serializer):
    api_version = serializers.CharField()
    site_name = serializers.CharField()
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    content_count = serializers.IntegerField()
    has_content = serializers.BooleanField()
    sequence_in_ms_min = serializers.IntegerField(allow_null=True)
    sequence_in_ms_max = serializers.IntegerField(allow_null=True)
    last_modified = serializers.DateTimeField(allow_null=True)


class ContentBulkRequestSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.JSONField(),
        help_text='Content rows. A bare JSON list is also accepted as the request body.',
    )
    mode = serializers.ChoiceField(
        choices=['append', 'replace'], default='append', required=False,
        help_text='"replace" deletes the manuscript\'s existing content first.',
    )
    dry_run = serializers.BooleanField(
        default=False, required=False,
        help_text='Validate the whole payload and report problems without writing.',
    )
    strict = serializers.BooleanField(
        default=True, required=False,
        help_text='Reject unrecognised field names instead of ignoring them.',
    )


class ContentBulkResponseSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    site_name = serializers.CharField()
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    mode = serializers.CharField()
    dry_run = serializers.BooleanField()
    received = serializers.IntegerField()
    created = serializers.IntegerField()
    deleted = serializers.IntegerField()
    created_uuids = serializers.ListField(child=serializers.UUIDField(), required=False)
    errors = RowErrorSerializer(many=True)


class ContentListSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    manuscript_uuid = serializers.UUIDField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    next_offset = serializers.IntegerField(allow_null=True)
    results = serializers.ListField(child=serializers.JSONField())


class ModelBlockSerializer(serializers.Serializer):
    model = serializers.CharField()
    category = serializers.CharField(required=False)
    count = serializers.IntegerField(required=False)
    results = serializers.ListField(child=serializers.JSONField())


class ManuscriptPackageSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    site_name = serializers.CharField()
    manuscript_uuid = serializers.UUIDField()
    manuscript_name = serializers.CharField()
    model_count = serializers.IntegerField()
    record_count = serializers.IntegerField()
    models = ModelBlockSerializer(many=True)
    media_files = serializers.ListField(child=serializers.JSONField(), required=False)


class DictionaryListItemSerializer(serializers.Serializer):
    slug = serializers.CharField()
    model = serializers.CharField()
    verbose_name = serializers.CharField()
    count = serializers.IntegerField()
    url = serializers.CharField(required=False)


class DictionaryListSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    count = serializers.IntegerField()
    results = DictionaryListItemSerializer(many=True)


class DictionaryPageSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    slug = serializers.CharField()
    model = serializers.CharField()
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    next_offset = serializers.IntegerField(allow_null=True)
    results = serializers.ListField(child=serializers.JSONField())


class WhoAmISerializer(serializers.Serializer):
    api_version = serializers.CharField()
    site_name = serializers.CharField()
    authenticated = serializers.BooleanField()
    username = serializers.CharField(allow_null=True)
    display_name = serializers.CharField(allow_null=True)
    can_import = serializers.BooleanField(
        help_text='True when this account may create manuscripts and import content.',
    )


class RootSerializer(serializers.Serializer):
    api_version = serializers.CharField()
    site_name = serializers.CharField()
    documentation = serializers.CharField()
    endpoints = serializers.DictField(child=serializers.CharField())
