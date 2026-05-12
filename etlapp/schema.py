from drf_spectacular.utils import OpenApiExample
from rest_framework import serializers


class ETLErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ETLConflictSerializer(serializers.Serializer):
    model = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)
    object_uuid = serializers.UUIDField(required=False)
    current_version = serializers.IntegerField(required=False)
    incoming_version = serializers.IntegerField(required=False)
    differences = serializers.ListField(child=serializers.JSONField(), required=False)
    local = serializers.JSONField(required=False)
    incoming = serializers.JSONField(required=False)


class ETLConflictResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    conflict = ETLConflictSerializer(required=False)


class ETLDeletedRecordSerializer(serializers.Serializer):
    model_label = serializers.CharField()
    category = serializers.CharField()
    object_uuid = serializers.UUIDField()
    source_pk = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    deleted_at = serializers.DateTimeField()


class ETLDeletedRecordsResponseSerializer(serializers.Serializer):
    site_name = serializers.CharField()
    category = serializers.CharField()
    since = serializers.DateTimeField(allow_null=True)
    count = serializers.IntegerField()
    results = ETLDeletedRecordSerializer(many=True)


class ETLDeltaModelSerializer(serializers.Serializer):
    model = serializers.CharField()
    results = serializers.ListField(child=serializers.JSONField())


class ETLDeltaExportResponseSerializer(serializers.Serializer):
    site_name = serializers.CharField()
    category = serializers.CharField()
    since = serializers.DateTimeField(allow_null=True)
    model_count = serializers.IntegerField()
    record_count = serializers.IntegerField()
    models = ETLDeltaModelSerializer(many=True)


class ETLDeltaImportRequestSerializer(serializers.Serializer):
    models = ETLDeltaModelSerializer(many=True)


class ETLDeltaImportResponseSerializer(serializers.Serializer):
    category = serializers.CharField(required=False)
    requested = serializers.IntegerField(required=False)
    created = serializers.IntegerField(required=False)
    updated = serializers.IntegerField(required=False)
    skipped = serializers.IntegerField(required=False)
    deleted = serializers.IntegerField(required=False)
    missing = serializers.IntegerField(required=False)


class ETLStatusResponseSerializer(serializers.Serializer):
    site_name = serializers.CharField()
    role = serializers.CharField()
    master_url = serializers.CharField(allow_null=True)
    slave_urls = serializers.ListField(child=serializers.CharField())
    has_api_token = serializers.BooleanField()
    model_category_counts = serializers.DictField(child=serializers.IntegerField())


class ETLManuscriptListItemSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    sync_status = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    entry_date = serializers.DateTimeField(required=False)


class ETLManuscriptListResponseSerializer(serializers.Serializer):
    site_name = serializers.CharField(required=False)
    count = serializers.IntegerField()
    results = ETLManuscriptListItemSerializer(many=True)


class ETLManuscriptExportResponseSerializer(serializers.Serializer):
    site_name = serializers.CharField(required=False)
    category = serializers.CharField()
    manuscript_uuid = serializers.UUIDField()
    model_count = serializers.IntegerField(required=False)
    record_count = serializers.IntegerField(required=False)
    models = ETLDeltaModelSerializer(many=True)


class ETLManuscriptImportRequestSerializer(serializers.Serializer):
    models = ETLDeltaModelSerializer(many=True)


class ETLManuscriptImportResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField(required=False)
    updated = serializers.IntegerField(required=False)
    skipped = serializers.IntegerField(required=False)
    manuscript_uuid = serializers.UUIDField(required=False)


ETL_STATUS_EXAMPLE = OpenApiExample(
    'ETL status',
    value={
        'site_name': 'Monumenta Poloniae Liturgica',
        'role': 'master',
        'master_url': None,
        'slave_urls': ['https://ecatalogus.ispan.pl'],
        'has_api_token': True,
        'model_category_counts': {'main': 34, 'shared': 4, 'ms': 28, 'local': 5},
    },
    response_only=True,
)


ETL_MAIN_EXPORT_EXAMPLE = OpenApiExample(
    'Main delta export',
    value={
        'site_name': 'Monumenta Poloniae Liturgica',
        'category': 'main',
        'since': '2026-05-08T10:00:00Z',
        'model_count': 1,
        'record_count': 1,
        'models': [
            {
                'model': 'indexerapp.Type',
                'results': [
                    {
                        'uuid': '9c61dd43-1f58-45d3-8d35-c1fb0d7ab733',
                        'short_name': 'TP1',
                        'name': 'Imported Type',
                        'entry_date': '2026-05-08T10:30:00Z',
                    }
                ],
            }
        ],
    },
    response_only=True,
)


ETL_SHARED_CONFLICT_EXAMPLE = OpenApiExample(
    'Shared conflict',
    value={
        'detail': 'Conflict for indexerapp.Bibliography uuid=9c61dd43-1f58-45d3-8d35-c1fb0d7ab733: incoming version 1 is older than local version 2.',
        'conflict': {
            'model': 'indexerapp.Bibliography',
            'reason': 'stale_version',
            'object_uuid': '9c61dd43-1f58-45d3-8d35-c1fb0d7ab733',
            'current_version': 2,
            'incoming_version': 1,
            'differences': [
                {'field': 'title', 'local': 'Current title v2', 'incoming': 'Stale title'},
            ],
        },
    },
    response_only=True,
    status_codes=['409'],
)


ETL_MANUSCRIPT_EXPORT_EXAMPLE = OpenApiExample(
    'Manuscript package export',
    value={
        'site_name': 'Monumenta Poloniae Liturgica',
        'category': 'ms',
        'manuscript_uuid': '0b7622ff-91aa-46c0-a618-124cfc6fca2e',
        'model_count': 2,
        'record_count': 2,
        'models': [
            {
                'model': 'indexerapp.Manuscripts',
                'results': [
                    {
                        'uuid': '0b7622ff-91aa-46c0-a618-124cfc6fca2e',
                        'name': 'MS Export',
                        'sync_status': 'ready',
                    }
                ],
            },
            {
                'model': 'indexerapp.Content',
                'results': [
                    {
                        'uuid': '113baaf7-7154-4a29-b01b-1959e39ee7a9',
                        'manuscript_uuid': '0b7622ff-91aa-46c0-a618-124cfc6fca2e',
                        'formula_text': 'Lorem ipsum',
                    }
                ],
            },
        ],
    },
    response_only=True,
)