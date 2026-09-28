"""Request and response examples shown in the Swagger UI for API v1.

Read examples are real responses from the public instances (trimmed where a
payload is long); write examples come from the same endpoints run against a
test database. The ``rights`` block is left out of most of them — it is the
same on every read response and is shown once, on the manuscript list.
"""

from drf_spectacular.utils import OpenApiExample


RIGHTS_EXAMPLE = {
    'license': 'CC-BY-NC-4.0',
    'license_name': 'Creative Commons Attribution-NonCommercial 4.0 International',
    'license_url': 'https://creativecommons.org/licenses/by-nc/4.0/',
    'copyright': (
        'Copyright (c) 2024-2026 Instytut Sztuki Polskiej Akademii Nauk (PAN) '
        '- Polish Academy of Sciences.'
    ),
    'rights_holder': 'Instytut Sztuki Polskiej Akademii Nauk (PAN)',
    'rights_holder_url': 'https://ispan.pl/',
    'required_statement': (
        'Data from eCatalogus, Instytut Sztuki Polskiej Akademii Nauk (PAN). '
        'Used under CC BY-NC 4.0; not for commercial use.'
    ),
    'attribution': (
        'Data from eCatalogus, Instytut Sztuki Polskiej Akademii Nauk (PAN). '
        'Used under CC BY-NC 4.0; not for commercial use.'
    ),
    'accessed': '2026-09-28T11:57:02.113517+00:00',
    'source': 'https://limbo.monumenta-poloniae-liturgica.ispan.pl/api/v1/manuscripts/?search=Tinecense',
    'recommended_citation': (
        'MPL Limbo. Instytut Sztuki Polskiej Akademii Nauk (PAN). accessed 2026-09-28. '
        'https://limbo.monumenta-poloniae-liturgica.ispan.pl/api/v1/manuscripts/?search=Tinecense. '
        'Licensed under CC-BY-NC-4.0.'
    ),
}

MANUSCRIPT_UUID = '7c0a82e8-8a59-5362-95d3-5d70e879dbf8'


# -- identity ---------------------------------------------------------------

WHOAMI_EXAMPLES = [
    OpenApiExample(
        'Importer',
        summary='Valid credentials, may import',
        value={
            'api_version': 'v1', 'site_name': 'eCatalogus', 'authenticated': True,
            'username': 'akowalska', 'display_name': 'Anna Kowalska', 'can_import': True,
        },
        response_only=True,
    ),
    OpenApiExample(
        'No import rights',
        summary='Valid credentials, not in api_importers',
        value={
            'api_version': 'v1', 'site_name': 'eCatalogus', 'authenticated': True,
            'username': 'gosc', 'display_name': 'gosc', 'can_import': False,
        },
        response_only=True,
    ),
    OpenApiExample(
        'Anonymous',
        summary='No credentials sent',
        value={
            'api_version': 'v1', 'site_name': 'eCatalogus', 'authenticated': False,
            'username': None, 'display_name': None, 'can_import': False,
        },
        response_only=True,
    ),
    OpenApiExample(
        'Wrong password',
        value={'detail': 'Invalid username/password.'},
        response_only=True, status_codes=['401'],
    ),
]


# -- manuscripts ------------------------------------------------------------

MANUSCRIPT_LIST_EXAMPLES = [
    OpenApiExample(
        'Search',
        summary='GET /api/v1/manuscripts/?search=Tinecense (MPL Limbo)',
        value={
            'api_version': 'v1',
            'site_name': 'MPL Limbo',
            'count': 1,
            'limit': 100,
            'offset': 0,
            'next_offset': None,
            'results': [{
                'uuid': MANUSCRIPT_UUID,
                'name': 'Sacramentarium Tinecense',
                'rism_id': 'PL-Wn BOZ 8',
                'foreign_id': '127',
                'shelf_mark': 'Rps BOZ 8',
                'contemporary_repository_place_label': 'The National Library',
                'dating_label': 'XI med',
                'content_count': 1416,
                'entry_date': '2025-12-10T20:00:26.921052+00:00',
            }],
            'rights': RIGHTS_EXAMPLE,
        },
        response_only=True,
    ),
]

MANUSCRIPT_CREATE_EXAMPLES = [
    OpenApiExample(
        'Minimal',
        summary='Only the required field',
        value={'name': 'Graduale Cracoviense'},
        request_only=True,
    ),
    OpenApiExample(
        'Typical',
        summary='Relations given by name',
        value={
            'name': 'Graduale Cracoviense',
            'foreign_id': 'ritus-2291',
            'rism_id': 'PL-Kk 12',
            'shelf_mark': 'MS 12',
            'contemporary_repository_place': 'Biblioteka Narodowa',
            'dating': 'XIV',
            'main_script': 'Textualis',
            'iiif_manifest_url': 'https://example.org/iiif/ms12/manifest.json',
        },
        request_only=True,
    ),
    OpenApiExample(
        'Created',
        value={
            'uuid': '74bd9697-1afa-496d-a2a7-2f946ce26bd9',
            'name': 'Graduale Cracoviense',
            'foreign_id': 'ritus-2291',
            'content_count': 0,
            'entry_date': '2026-09-28T12:13:36.191153+00:00',
        },
        response_only=True, status_codes=['201'],
    ),
    OpenApiExample(
        'Unknown dictionary value',
        value={
            'detail': '1 problem(s) found; the manuscript was not created.',
            'errors': [{
                'row': 0,
                'field': 'dating',
                'value': 's. XXX',
                'error': 'not_found',
                'detail': (
                    'No TimeReference entry matches "s. XXX" (matched against: time_description). '
                    'Dictionary entries must exist before content referencing them is imported.'
                ),
            }],
        },
        response_only=True, status_codes=['400'],
    ),
    OpenApiExample(
        'Not signed in',
        value={'detail': 'Authentication credentials were not provided.'},
        response_only=True, status_codes=['401'],
    ),
    OpenApiExample(
        'No import rights',
        value={'detail': 'You do not have permission to modify catalogue data.'},
        response_only=True, status_codes=['403'],
    ),
]


# -- content ----------------------------------------------------------------

CONTENT_SUMMARY_EXAMPLES = [
    OpenApiExample(
        'Has content',
        summary='Sacramentarium Tinecense (MPL Limbo)',
        value={
            'api_version': 'v1',
            'site_name': 'MPL Limbo',
            'manuscript_uuid': MANUSCRIPT_UUID,
            'manuscript_name': 'Sacramentarium Tinecense',
            'content_count': 1416,
            'has_content': True,
            'sequence_in_ms_min': 1,
            'sequence_in_ms_max': 1416,
            'last_modified': '2024-12-04T20:04:18.805394+00:00',
        },
        response_only=True,
    ),
    OpenApiExample(
        'Unknown manuscript',
        value={'detail': 'No manuscript with uuid 00000000-0000-0000-0000-000000000000.'},
        response_only=True, status_codes=['404'],
    ),
]

CONTENT_ROW_EXAMPLE = {
    'uuid': '11b726a0-6ac5-5478-8aa4-572490629e8c',
    'manuscript_uuid': MANUSCRIPT_UUID,
    'sequence_in_ms': 11,
    'rubric_sequence_in_the_MS': None,
    'rubric_name_from_ms': 'Missa pro rege et exercitu eius',
    'subrubric_name_from_ms': None,
    'formula_text_from_ms': None,
    'where_in_ms_from': '5',
    'where_in_ms_to': '6',
    'digital_page_number': None,
    'original_or_added': 'ADDED',
    'biblical_reference': None,
    'reference_to_other_items': None,
    'similarity_by_user': '0',
    'edition_subindex': None,
    'comments': None,
    'proper_texts': None,
    'formula_id': '2f1a32fb-721b-5655-9865-1b10eea70a10',
    'formula_label': '2046',
    'rubric_id': None,
    'rubric_label': None,
    'liturgical_genre_id': None,
    'liturgical_genre_label': None,
    'function_id': '85d62046-5521-5150-aa23-799de39d44f9',
    'function_label': 'Collecta',
    'contributor_id': '86c8f363-c223-5a50-89ba-b57d72dad5cf',
    'contributor_label': 'PF',
    'entry_date': '2024-12-04T20:04:14.824768+00:00',
}

CONTENT_LIST_EXAMPLES = [
    OpenApiExample(
        'One page',
        summary='GET …/content/?limit=1&offset=10 (Sacramentarium Tinecense, trimmed)',
        description='Keys with null values for every relation not shown here are also present.',
        value={
            'api_version': 'v1',
            'manuscript_uuid': MANUSCRIPT_UUID,
            'manuscript_name': 'Sacramentarium Tinecense',
            'count': 1416,
            'limit': 1,
            'offset': 10,
            'next_offset': 11,
            'results': [CONTENT_ROW_EXAMPLE],
        },
        response_only=True,
    ),
]

CONTENT_BULK_EXAMPLES = [
    OpenApiExample(
        'Validate first',
        summary='Dry run with names instead of UUIDs',
        value={
            'items': [
                {
                    'sequence_in_ms': 1,
                    'where_in_ms_from': '5',
                    'where_in_ms_to': '6',
                    'rubric_name_from_ms': 'Missa pro rege et exercitu eius',
                    'rubric_id': 'pro rege',
                    'formula_id': '2f1a32fb-721b-5655-9865-1b10eea70a10',
                    'function_id': 'Collecta',
                    'original_or_added': 'ADDED',
                },
                {
                    'sequence_in_ms': 2,
                    'where_in_ms_from': '6',
                    'function_id': 'Secreta',
                    'formula_text_from_ms': 'Munera domine quaesumus oblata sanctifica',
                },
            ],
            'mode': 'append',
            'dry_run': True,
        },
        request_only=True,
    ),
    OpenApiExample(
        'Bare list',
        summary='Legacy shape: the body is just the list of rows',
        value=[{'formula_text_from_ms': 'Per omnia saecula saeculorum', 'where_in_ms_from': '12v'}],
        request_only=True,
    ),
    OpenApiExample(
        'Re-upload',
        summary='Replace everything the manuscript had',
        value={'items': [{'sequence_in_ms': 1, 'function_id': 'Collecta'}], 'mode': 'replace'},
        request_only=True,
    ),
    OpenApiExample(
        'Dry run passed',
        value={
            'api_version': 'v1', 'site_name': 'eCatalogus',
            'manuscript_uuid': '74bd9697-1afa-496d-a2a7-2f946ce26bd9',
            'manuscript_name': 'Graduale Cracoviense',
            'mode': 'append', 'dry_run': True,
            'received': 2, 'created': 0, 'deleted': 0, 'errors': [],
            'detail': 'Payload is valid. Nothing was written because dry_run was set.',
        },
        response_only=True, status_codes=['200'],
    ),
    OpenApiExample(
        'Imported',
        value={
            'api_version': 'v1', 'site_name': 'eCatalogus',
            'manuscript_uuid': '74bd9697-1afa-496d-a2a7-2f946ce26bd9',
            'manuscript_name': 'Graduale Cracoviense',
            'mode': 'append', 'dry_run': False,
            'received': 2, 'created': 2, 'deleted': 0, 'errors': [],
            'created_uuids': [
                'e667f9b1-3f41-4be1-8721-58104ffd986f',
                'f224a6fe-b1a3-45d9-9667-1693c4895259',
            ],
        },
        response_only=True, status_codes=['200'],
    ),
    OpenApiExample(
        'Rejected',
        summary='Rubric confused with a function, a typo, a wrong type and an unknown key',
        value={
            'detail': '4 problem(s) found; nothing was imported.',
            'errors': [
                {
                    'row': 0, 'field': 'rubric_id', 'value': 'Ad complendum', 'error': 'not_found',
                    'detail': (
                        'No RiteNames entry matches "Ad complendum" (matched against: name). '
                        'Dictionary entries must exist before content referencing them is imported.'
                    ),
                },
                {
                    'row': 1, 'field': 'folio', 'value': '7v', 'error': 'unknown_field',
                    'detail': '"folio" is not a recognised content field.',
                },
                {
                    'row': 1, 'field': 'sequence_in_ms', 'value': 'twelve', 'error': 'invalid_value',
                    'detail': 'expected a whole number, got "twelve"',
                },
                {
                    'row': 1, 'field': 'function_id', 'value': 'Colecta', 'error': 'not_found',
                    'detail': (
                        'No ContentFunctions entry matches "Colecta" (matched against: name). '
                        'Dictionary entries must exist before content referencing them is imported.'
                    ),
                },
            ],
        },
        response_only=True, status_codes=['400'],
    ),
    OpenApiExample(
        'Not signed in',
        value={'detail': 'Authentication credentials were not provided.'},
        response_only=True, status_codes=['401'],
    ),
    OpenApiExample(
        'No import rights',
        value={'detail': 'You do not have permission to access this endpoint.'},
        response_only=True, status_codes=['403'],
    ),
]


# -- package ----------------------------------------------------------------

PACKAGE_EXAMPLES = [
    OpenApiExample(
        'Small manuscript',
        summary='Antiphonarium, PL-WRu I F 405 (MPL Limbo; null fields trimmed)',
        value={
            'site_name': 'MPL Limbo',
            'category': 'ms',
            'manuscript_uuid': '28d56828-30eb-45fe-9034-d3d7d6e88d12',
            'manuscript_name': 'Antiphonarium',
            'model_count': 2,
            'record_count': 2,
            'models': [
                {
                    'model': 'indexerapp.Manuscripts', 'category': 'ms', 'count': 1,
                    'results': [{
                        'uuid': '28d56828-30eb-45fe-9034-d3d7d6e88d12',
                        'name': 'Antiphonarium',
                        'rism_id': 'PL-WRu I F 405',
                        'foreign_id': 'MSPL 5197',
                        'contemporary_repository_place_uuid': 'eb09cafc-bde0-5f5a-89b7-014fd6a47eae',
                        'contemporary_repository_place_label': 'University Library',
                        'shelf_mark': 'I F 405',
                        'dating_uuid': '93b1b867-a1b7-5d66-a378-1ce3bca34624',
                        'dating_label': 'XIII',
                        'image': 'images/Zrzut_ekranu_2026-07-1_o_10.22.40.png',
                        'data_contributor_uuid': 'f34f11c0-9d7d-5041-ba01-cd9c99e3a167',
                        'data_contributor_label': 'PPŻ',
                        'entry_date': '2026-07-01T08:26:44.682389+00:00',
                    }],
                },
                {
                    'model': 'indexerapp.MSProjects', 'category': 'ms', 'count': 1,
                    'results': [{
                        'uuid': '4497f26e-5d6b-485a-8e0a-e46cf96a8d86',
                        'manuscript_uuid': '28d56828-30eb-45fe-9034-d3d7d6e88d12',
                        'manuscript_label': 'Antiphonarium',
                        'project_uuid': '7762c02f-8d5c-5bde-8924-8e6fa3ee2650',
                        'project_label': 'Liturgica Poloniae',
                        'entry_date': '2026-06-02T09:22:09.818011+00:00',
                    }],
                },
            ],
            'media_files': [{
                'path': 'images/Zrzut_ekranu_2026-07-1_o_10.22.40.png',
                'size': 3652450,
                'url': (
                    'https://limbo.monumenta-poloniae-liturgica.ispan.pl'
                    '/media/images/Zrzut_ekranu_2026-07-1_o_10.22.40.png'
                ),
            }],
            'api_version': 'v1',
        },
        response_only=True,
    ),
]


# -- dictionaries -----------------------------------------------------------

DICTIONARY_LIST_EXAMPLES = [
    OpenApiExample(
        'Vocabularies',
        summary='First entries of GET /api/v1/dictionaries/ (32 in total)',
        value={
            'api_version': 'v1',
            'count': 32,
            'results': [
                {
                    'slug': 'content-functions', 'model': 'indexerapp.ContentFunctions',
                    'verbose_name': 'Content functions', 'count': 113,
                    'url': 'https://ecatalogus.ispan.pl/api/v1/dictionaries/content-functions/',
                },
                {
                    'slug': 'formulas', 'model': 'indexerapp.Formulas',
                    'verbose_name': 'Formulas', 'count': 13234,
                    'url': 'https://ecatalogus.ispan.pl/api/v1/dictionaries/formulas/',
                },
                {
                    'slug': 'rite-names', 'model': 'indexerapp.RiteNames',
                    'verbose_name': 'Rite Names Standarized', 'count': 4564,
                    'url': 'https://ecatalogus.ispan.pl/api/v1/dictionaries/rite-names/',
                },
            ],
        },
        response_only=True,
    ),
]

DICTIONARY_PAGE_EXAMPLES = [
    OpenApiExample(
        'Search',
        summary='GET /api/v1/dictionaries/formulas/?search=2046&fields=co_no,text',
        value={
            'api_version': 'v1', 'slug': 'formulas', 'model': 'indexerapp.Formulas',
            'count': 2, 'limit': 200, 'offset': 0, 'next_offset': None,
            'results': [
                {
                    'uuid': 'ee19d899-310c-5f7a-8bd8-c3c5317ad835', 'id': 2658, 'co_no': '2046',
                    'text': 'Pax huic domui. 〈R.〉 Pax intrantibus et coquentibus in ea.',
                },
                {
                    'uuid': '2f1a32fb-721b-5655-9865-1b10eea70a10', 'id': 7543, 'co_no': '2046',
                    'text': (
                        'Deus qui regnorum omnium regumque es dominator supplicationes nostras '
                        'clementer exaudi …'
                    ),
                },
            ],
        },
        response_only=True,
    ),
    OpenApiExample(
        'Legacy ids',
        summary='GET /api/v1/dictionaries/formulas/?legacy_ids=1,2,999999&fields=co_no',
        value={
            'api_version': 'v1', 'slug': 'formulas', 'model': 'indexerapp.Formulas',
            'count': 1, 'limit': 1000, 'offset': 0, 'next_offset': None,
            'results': [{
                'uuid': '44064845-17c3-5f94-9756-93588ebfa2e0', 'id': 1, 'legacy_id': 1, 'co_no': '2',
            }],
            'unresolved_legacy_ids': [2, 999999],
        },
        response_only=True,
    ),
    OpenApiExample(
        'Unknown parameter',
        value={
            'detail': (
                'Unknown query parameter(s): q. This endpoint accepts: fields, format, '
                'legacy_ids, limit, offset, search, since, uuids.'
            ),
        },
        response_only=True, status_codes=['400'],
    ),
    OpenApiExample(
        'Unknown vocabulary',
        value={'detail': 'Unknown dictionary "nope".'},
        response_only=True, status_codes=['404'],
    ),
]
