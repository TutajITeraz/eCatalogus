import csv
import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import Permission, User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from etlapp.services import ETLImportConflictError, _serialize_value, build_manuscript_export_payload, import_manuscript_payload
from etlapp.uuid_utils import build_deterministic_sync_uuid
from indexerapp.models import Bibliography, Colours, Content, ContentTopic, Contributors, DeletedRecord, EditionContent, Formulas, LiturgicalGenres, Manuscripts, MassHour, Topic, Traditions, Type, Watermarks


ETL_UI_PERMISSION_CODENAMES = [
    'add_manuscripts',
    'add_content',
    'add_bibliography',
    'add_editioncontent',
    'add_formulas',
    'add_ritenames',
    'add_timereference',
]


class ETLUIEditorMixin:
    def create_editor_user(self):
        user = User.objects.create_user(username='etl-editor', password='secret123A')
        permissions = Permission.objects.filter(
            content_type__app_label='indexerapp',
            codename__in=ETL_UI_PERMISSION_CODENAMES,
        )
        user.user_permissions.add(*permissions)
        return user


@override_settings(
    SITE_NAME='Test Site',
    ETL_ROLE='master',
    ETL_MASTER_URL=None,
    ETL_SLAVE_URLS=['http://127.0.0.1:8080'],
    ETL_API_TOKEN='test-token',
)
class ETLStatusViewTests(SimpleTestCase):
    def test_status_endpoint_requires_authentication(self):
        client = APIClient()

        response = client.get(reverse('etl:etl-status'))

        self.assertEqual(response.status_code, 401)

    def test_status_endpoint_returns_instance_metadata(self):
        client = APIClient()

        response = client.get(reverse('etl:etl-status'), HTTP_AUTHORIZATION='Token test-token')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['site_name'], 'Test Site')
        self.assertEqual(response.json()['role'], 'master')
        self.assertTrue(response.json()['has_api_token'])


@override_settings(
    SITE_NAME='Test Site',
    ETL_ROLE='master',
    ETL_MASTER_URL=None,
    ETL_SLAVE_URLS=['http://127.0.0.1:8080'],
    ETL_API_TOKEN='test-token',
)
class ETLDeletedRecordsViewTests(TestCase):
    def test_deleted_endpoint_returns_category_records_filtered_by_since(self):
        older = DeletedRecord.objects.create(
            model_label='indexerapp.Bibliography',
            category='shared',
            object_uuid=uuid4(),
            source_pk='1',
        )
        recent = DeletedRecord.objects.create(
            model_label='indexerapp.Contributors',
            category='shared',
            object_uuid=uuid4(),
            source_pk='2',
        )
        DeletedRecord.objects.filter(pk=older.pk).update(deleted_at=timezone.now() - timezone.timedelta(days=2))
        DeletedRecord.objects.filter(pk=recent.pk).update(deleted_at=timezone.now() - timezone.timedelta(hours=1))

        client = APIClient()
        response = client.get(
            reverse('etl:etl-deleted-records', kwargs={'category': 'shared'}),
            {'since': (timezone.now() - timezone.timedelta(days=1)).isoformat()},
            HTTP_AUTHORIZATION='Bearer test-token',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['category'], 'shared')
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['model_label'], 'indexerapp.Contributors')

    def test_deleted_endpoint_rejects_invalid_since_value(self):
        client = APIClient()

        response = client.get(
            reverse('etl:etl-deleted-records', kwargs={'category': 'shared'}),
            {'since': 'not-a-date'},
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 400)

    def test_deleted_endpoint_rejects_invalid_category(self):
        client = APIClient()

        response = client.get(
            reverse('etl:etl-deleted-records', kwargs={'category': 'local'}),
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 404)


@override_settings(
    SITE_NAME='Test Site',
    ETL_ROLE='master',
    ETL_MASTER_URL=None,
    ETL_SLAVE_URLS=['http://127.0.0.1:8080'],
    ETL_API_TOKEN='test-token',
)
class ETLDeltaExportViewTests(TestCase):
    def test_main_export_returns_recent_records(self):
        older = Type.objects.create(short_name='A', name='Alpha')
        recent = Type.objects.create(short_name='B', name='Beta')
        Type.objects.filter(pk=older.pk).update(entry_date=timezone.now() - timezone.timedelta(days=3))
        Type.objects.filter(pk=recent.pk).update(entry_date=timezone.now() - timezone.timedelta(hours=2))

        client = APIClient()
        response = client.get(
            reverse('etl:etl-delta-export', kwargs={'category': 'main'}),
            {'since': (timezone.now() - timezone.timedelta(days=1)).isoformat()},
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['category'], 'main')
        self.assertEqual(payload['model_count'], 1)
        self.assertEqual(payload['record_count'], 1)
        self.assertEqual(payload['models'][0]['model'], 'indexerapp.Type')
        self.assertEqual(payload['models'][0]['results'][0]['name'], 'Beta')
        self.assertIsNotNone(payload['models'][0]['results'][0]['uuid'])

    def test_shared_export_returns_versioned_rows(self):
        bibliography = Bibliography.objects.create(title='Shared row')

        client = APIClient()
        response = client.get(
            reverse('etl:etl-delta-export', kwargs={'category': 'shared'}),
            HTTP_AUTHORIZATION='Bearer test-token',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['category'], 'shared')
        self.assertEqual(payload['record_count'], 1)
        exported = payload['models'][0]['results'][0]
        self.assertEqual(exported['title'], 'Shared row')
        self.assertEqual(exported['version'], bibliography.version)
        self.assertIsNotNone(exported['uuid'])

    def test_export_rejects_unsupported_category(self):
        client = APIClient()

        response = client.get(
            reverse('etl:etl-delta-export', kwargs={'category': 'ms'}),
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 404)


@override_settings(
    SITE_NAME='Test Site',
    ETL_ROLE='master',
    ETL_MASTER_URL=None,
    ETL_SLAVE_URLS=['http://127.0.0.1:8080'],
    ETL_API_TOKEN='test-token',
)
class ETLDeltaImportViewTests(TestCase):
    def test_main_import_creates_records_and_resolves_foreign_keys_by_uuid(self):
        imported_type_uuid = str(uuid4())
        imported_mass_hour_uuid = str(uuid4())

        client = APIClient()
        response = client.post(
            reverse('etl:etl-delta-import', kwargs={'category': 'main'}),
            {
                'models': [
                    {
                        'model': 'indexerapp.Type',
                        'results': [
                            {
                                'uuid': imported_type_uuid,
                                'short_name': 'TP1',
                                'name': 'Imported Type',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                    {
                        'model': 'indexerapp.MassHour',
                        'results': [
                            {
                                'uuid': imported_mass_hour_uuid,
                                'short_name': 'MH1',
                                'name': 'Imported MassHour',
                                'type_uuid': imported_type_uuid,
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                ],
            },
            format='json',
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 200)
        imported_type = Type.objects.get(uuid=imported_type_uuid)
        imported_mass_hour = MassHour.objects.get(uuid=imported_mass_hour_uuid)
        self.assertEqual(imported_type.name, 'Imported Type')
        self.assertEqual(imported_mass_hour.type_id, imported_type.pk)
        self.assertEqual(response.json()['created'], 2)

    def test_shared_import_updates_when_version_is_newer(self):
        bibliography = Bibliography.objects.create(title='Old title')

        client = APIClient()
        response = client.post(
            reverse('etl:etl-delta-import', kwargs={'category': 'shared'}),
            {
                'models': [
                    {
                        'model': 'indexerapp.Bibliography',
                        'results': [
                            {
                                'uuid': str(bibliography.uuid),
                                'title': 'New title',
                                'author': None,
                                'shortname': None,
                                'year': None,
                                'zotero_id': None,
                                'hierarchy': None,
                                'version': bibliography.version + 1,
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    }
                ],
            },
            format='json',
            HTTP_AUTHORIZATION='Bearer test-token',
        )

        self.assertEqual(response.status_code, 200)
        bibliography.refresh_from_db()
        self.assertEqual(bibliography.title, 'New title')
        self.assertEqual(bibliography.version, 2)
        self.assertEqual(response.json()['updated'], 1)

    def test_shared_import_returns_conflict_for_stale_version(self):
        bibliography = Bibliography.objects.create(title='Current title')
        bibliography.title = 'Current title v2'
        bibliography.save()

        client = APIClient()
        response = client.post(
            reverse('etl:etl-delta-import', kwargs={'category': 'shared'}),
            {
                'models': [
                    {
                        'model': 'indexerapp.Bibliography',
                        'results': [
                            {
                                'uuid': str(bibliography.uuid),
                                'title': 'Stale title',
                                'author': None,
                                'shortname': None,
                                'year': None,
                                'zotero_id': None,
                                'hierarchy': None,
                                'version': 1,
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    }
                ],
            },
            format='json',
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload['conflict']['model'], 'indexerapp.Bibliography')
        self.assertEqual(payload['conflict']['reason'], 'stale_version')
        self.assertEqual(payload['conflict']['object_uuid'], str(bibliography.uuid))

    def test_shared_import_skips_identical_watermark_with_empty_image_field(self):
        contributor = Contributors.objects.create(
            initials='AB',
            first_name='Anna',
            last_name='Baker',
        )
        watermark = Watermarks.objects.create(
            name='Shared watermark',
            comment='',
            watermark_img=None,
            data_contributor=contributor,
        )
        watermark.authors.add(contributor)

        client = APIClient()
        response = client.post(
            reverse('etl:etl-delta-import', kwargs={'category': 'shared'}),
            {
                'models': [
                    {
                        'model': 'indexerapp.Contributors',
                        'results': [
                            {
                                'uuid': str(contributor.uuid),
                                'initials': contributor.initials,
                                'first_name': contributor.first_name,
                                'last_name': contributor.last_name,
                                'affiliation': contributor.affiliation,
                                'email': contributor.email,
                                'url': contributor.url,
                                'version': contributor.version,
                                'entry_date': contributor.entry_date.isoformat(),
                            }
                        ],
                    },
                    {
                        'model': 'indexerapp.Watermarks',
                        'results': [
                            {
                                'uuid': str(watermark.uuid),
                                'name': watermark.name,
                                'external_id': watermark.external_id,
                                'watermark_img': None,
                                'comment': watermark.comment,
                                'entry_date': watermark.entry_date.isoformat(),
                                'version': watermark.version,
                                'data_contributor_uuid': str(contributor.uuid),
                                'authors_uuids': [str(contributor.uuid)],
                            }
                        ],
                    },
                ],
            },
            format='json',
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['updated'], 0)
        self.assertEqual(response.json()['skipped'], 2)


@override_settings(
    SITE_NAME='Test Site',
    ETL_ROLE='master',
    ETL_MASTER_URL=None,
    ETL_SLAVE_URLS=['http://127.0.0.1:8080'],
    ETL_API_TOKEN='test-token',
)
class ETLManuscriptPackageViewTests(TestCase):
    def test_manuscript_list_returns_sync_metadata(self):
        manuscript = Manuscripts.objects.create(name='MS One', sync_status='ready')

        client = APIClient()
        response = client.get(
            reverse('etl:etl-manuscript-list'),
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['uuid'], str(manuscript.uuid))
        self.assertEqual(payload['results'][0]['sync_status'], 'ready')

    def test_manuscript_export_returns_package_with_dependent_ms_models(self):
        manuscript = Manuscripts.objects.create(name='MS Export')
        content = Content.objects.create(manuscript=manuscript, formula_text='Lorem ipsum')
        topic = Topic.objects.create(name='Topic A')
        content_topic = ContentTopic.objects.create(content=content, topic=topic)

        client = APIClient()
        response = client.get(
            reverse('etl:etl-manuscript-export', kwargs={'manuscript_uuid': manuscript.uuid}),
            HTTP_AUTHORIZATION='Bearer test-token',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['category'], 'ms')
        self.assertEqual(payload['manuscript_uuid'], str(manuscript.uuid))
        models_by_label = {model_payload['model']: model_payload for model_payload in payload['models']}
        self.assertIn('indexerapp.Manuscripts', models_by_label)
        self.assertIn('indexerapp.Content', models_by_label)
        self.assertIn('indexerapp.ContentTopic', models_by_label)
        exported_content_topic = models_by_label['indexerapp.ContentTopic']['results'][0]
        self.assertEqual(exported_content_topic['uuid'], str(content_topic.uuid))
        self.assertEqual(exported_content_topic['content_uuid'], str(content.uuid))

    def test_manuscript_import_creates_ms_package(self):
        manuscript_uuid = str(uuid4())
        content_uuid = str(uuid4())

        client = APIClient()
        response = client.post(
            reverse('etl:etl-manuscript-import'),
            {
                'models': [
                    {
                        'model': 'indexerapp.Manuscripts',
                        'results': [
                            {
                                'uuid': manuscript_uuid,
                                'name': 'Imported manuscript',
                                'sync_status': 'ready',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                    {
                        'model': 'indexerapp.Content',
                        'results': [
                            {
                                'uuid': content_uuid,
                                'manuscript_uuid': manuscript_uuid,
                                'formula_text': 'Imported content',
                                'where_in_ms_from': '1r',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                ],
            },
            format='json',
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 200)
        manuscript = Manuscripts.objects.get(uuid=manuscript_uuid)
        content = Content.objects.get(uuid=content_uuid)
        self.assertEqual(manuscript.name, 'Imported manuscript')
        self.assertEqual(content.manuscript_id, manuscript.pk)
        self.assertEqual(response.json()['category'], 'ms')
        self.assertEqual(response.json()['created'], 2)


class ExportModelCategoriesCommandTests(TestCase):
    def test_export_model_categories_writes_expected_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'etl_model_categories.tsv'

            call_command('export_model_categories', output=str(output_path))

            self.assertTrue(output_path.exists())
            with output_path.open('r', encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))

        self.assertTrue(any(row['model_name'] == 'Manuscripts' for row in rows))
        manuscripts_row = next(row for row in rows if row['model_name'] == 'Manuscripts')
        self.assertEqual(manuscripts_row['category'], 'ms')
        self.assertEqual(manuscripts_row['sync_enabled'], 'yes')
        self.assertIn('data_contributor', manuscripts_row['foreign_keys'])
        self.assertIn('dependency_batch', manuscripts_row)
        self.assertIn('sync_fk_dependencies', manuscripts_row)

        projects_row = next(row for row in rows if row['model_name'] == 'Projects')
        self.assertEqual(projects_row['category'], 'main')
        self.assertEqual(projects_row['sync_enabled'], 'yes')

        ms_projects_row = next(row for row in rows if row['model_name'] == 'MSProjects')
        self.assertEqual(ms_projects_row['category'], 'ms')
        self.assertEqual(ms_projects_row['sync_enabled'], 'yes')

    def test_export_uuid_fk_plan_writes_sync_foreign_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'etl_uuid_fk_plan.tsv'

            call_command('export_uuid_fk_plan', output=str(output_path))

            self.assertTrue(output_path.exists())
            with output_path.open('r', encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))

        bibliography_fk = next(
            row for row in rows
            if row['model_name'] == 'ManuscriptBibliography' and row['fk_field'] == 'bibliography'
        )
        self.assertEqual(bibliography_fk['related_model'], 'Bibliography')
        self.assertEqual(bibliography_fk['related_has_uuid'], 'yes')
        self.assertEqual(bibliography_fk['suggested_uuid_field'], 'bibliography_uuid')

        manuscript_fk = next(
            row for row in rows
            if row['model_name'] == 'Content' and row['fk_field'] == 'manuscript'
        )
        self.assertEqual(manuscript_fk['related_model'], 'Manuscripts')
        self.assertEqual(manuscript_fk['model_category'], 'ms')

    def test_export_etl_bundle_writes_main_json_bundle(self):
        Type.objects.create(short_name='TP1', name='Type One')

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'main_bundle.json'

            call_command('export_etl_bundle', '--category', 'main', '--output', str(output_path))

            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding='utf-8'))

        self.assertEqual(payload['category'], 'main')
        self.assertEqual(payload['model_count'], 1)
        self.assertEqual(payload['record_count'], 1)
        self.assertEqual(payload['models'][0]['model'], 'indexerapp.Type')
        self.assertEqual(payload['models'][0]['results'][0]['short_name'], 'TP1')

    def test_import_etl_bundle_imports_main_json_bundle(self):
        payload = {
            'category': 'main',
            'models': [
                {
                    'model': 'indexerapp.Type',
                    'results': [
                        {
                            'uuid': str(uuid4()),
                            'short_name': 'TP2',
                            'name': 'Imported bundle',
                            'entry_date': timezone.now().isoformat(),
                        }
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / 'main_bundle.json'
            input_path.write_text(json.dumps(payload), encoding='utf-8')

            stdout = StringIO()
            call_command('import_etl_bundle', str(input_path), stdout=stdout)

        self.assertTrue(Type.objects.filter(short_name='TP2', name='Imported bundle').exists())
        self.assertIn('Imported bundle', Type.objects.get(short_name='TP2').name)
        self.assertIn('"created": 1', stdout.getvalue())

    def test_import_legacy_main_bundle_handles_self_referential_parent(self):
        parent_uuid = str(uuid4())
        child_uuid = str(uuid4())
        payload = {
            'site_name': 'legacy-main-bootstrap',
            'category': 'main',
            'legacy_source': True,
            'uuid_strategy': 'deterministic:model_label+pk',
            'model_count': 1,
            'record_count': 2,
            'models': [
                {
                    'model': 'indexerapp.Colours',
                    'category': 'main',
                    'count': 2,
                    'results': [
                        {
                            'source_pk': 2,
                            'uuid': child_uuid,
                            'name': 'Child colour',
                            'rgb': '#123456',
                            'parent_colour': 1,
                            'parent_colour_uuid': parent_uuid,
                        },
                        {
                            'source_pk': 1,
                            'uuid': parent_uuid,
                            'name': 'Parent colour',
                            'rgb': '#abcdef',
                            'parent_colour': None,
                            'parent_colour_uuid': None,
                        },
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / 'legacy_main_bundle.json'
            input_path.write_text(json.dumps(payload), encoding='utf-8')

            stdout = StringIO()
            call_command('import_legacy_main_bundle', str(input_path), stdout=stdout)

        parent = Colours.objects.get(uuid=parent_uuid)
        child = Colours.objects.get(uuid=child_uuid)
        self.assertEqual(child.parent_colour, parent)
        self.assertIn('"created": 2', stdout.getvalue())

    def test_import_legacy_main_bundle_handles_self_parent_reference(self):
        colour_uuid = str(uuid4())
        payload = {
            'site_name': 'legacy-main-bootstrap',
            'category': 'main',
            'legacy_source': True,
            'uuid_strategy': 'deterministic:model_label+pk',
            'model_count': 1,
            'record_count': 1,
            'models': [
                {
                    'model': 'indexerapp.Colours',
                    'category': 'main',
                    'count': 1,
                    'results': [
                        {
                            'source_pk': 1,
                            'uuid': colour_uuid,
                            'name': 'Self colour',
                            'rgb': '#123456',
                            'parent_colour': 1,
                            'parent_colour_uuid': colour_uuid,
                        },
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / 'legacy_main_bundle.json'
            input_path.write_text(json.dumps(payload), encoding='utf-8')

            stdout = StringIO()
            call_command('import_legacy_main_bundle', str(input_path), stdout=stdout)

        colour = Colours.objects.get(uuid=colour_uuid)
        self.assertEqual(colour.parent_colour, colour)
        self.assertIn('"created": 1', stdout.getvalue())

    def test_export_legacy_main_bundle_includes_shared_dependencies_for_edition_content(self):
        bibliography = Bibliography.objects.create(title='Bib one', uuid=None)
        EditionContent.objects.create(bibliography=bibliography, uuid=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'legacy_main_bundle.json'

            call_command('export_legacy_main_bundle', '--output', str(output_path))
            payload = json.loads(output_path.read_text(encoding='utf-8'))

        shared_models = {item['model'] for item in payload['shared_dependencies']}
        self.assertIn('indexerapp.Bibliography', shared_models)
        bibliography_payload = next(
            item for item in payload['shared_dependencies'] if item['model'] == 'indexerapp.Bibliography'
        )
        self.assertEqual(bibliography_payload['results'][0]['title'], 'Bib one')

    def test_import_legacy_main_bundle_imports_shared_dependencies_before_main(self):
        bibliography_uuid = str(uuid4())
        edition_uuid = str(uuid4())
        payload = {
            'site_name': 'legacy-main-bootstrap',
            'category': 'main',
            'legacy_source': True,
            'uuid_strategy': 'deterministic:model_label+pk',
            'model_count': 1,
            'record_count': 1,
            'shared_dependency_model_count': 1,
            'shared_dependency_record_count': 1,
            'shared_dependencies': [
                {
                    'model': 'indexerapp.Bibliography',
                    'category': 'shared',
                    'count': 1,
                    'results': [
                        {
                            'source_pk': 1,
                            'uuid': bibliography_uuid,
                            'title': 'Shared bibliography',
                            'author': 'Author',
                            'shortname': 'SB',
                            'year': 2024,
                            'zotero_id': None,
                            'hierarchy': None,
                            'version': 1,
                        }
                    ],
                }
            ],
            'models': [
                {
                    'model': 'indexerapp.EditionContent',
                    'category': 'main',
                    'count': 1,
                    'results': [
                        {
                            'source_pk': 1,
                            'uuid': edition_uuid,
                            'bibliography': 1,
                            'bibliography_uuid': bibliography_uuid,
                            'formula': None,
                            'formula_uuid': None,
                            'rubric_name_standarized': None,
                            'rubric_name_standarized_uuid': None,
                            'feast_rubric_sequence': '1.0',
                            'subsequence': None,
                            'page': 7,
                            'function': None,
                            'function_uuid': None,
                            'subfunction': None,
                            'subfunction_uuid': None,
                            'data_contributor': None,
                            'data_contributor_uuid': None,
                            'authors': [],
                            'authors_uuids': [],
                        }
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / 'legacy_main_bundle.json'
            input_path.write_text(json.dumps(payload), encoding='utf-8')

            stdout = StringIO()
            call_command('import_legacy_main_bundle', str(input_path), stdout=stdout)

        bibliography = Bibliography.objects.get(uuid=bibliography_uuid)
        edition_content = EditionContent.objects.get(uuid=edition_uuid)
        self.assertEqual(edition_content.bibliography, bibliography)
        self.assertIn('"shared_dependencies"', stdout.getvalue())

    def test_export_legacy_main_bundle_and_import_it_back(self):
        genre = LiturgicalGenres.objects.create(title='Antiphon')
        Traditions.objects.create(name='Roman', genre=genre, uuid=None)
        tradition = Traditions.objects.get(name='Roman')
        formula = Formulas.objects.create(co_no='CO123', text='Lorem', uuid=None)
        formula.tradition.add(tradition)

        LiturgicalGenres.objects.filter(pk=genre.pk).update(uuid=None)
        Traditions.objects.filter(pk=tradition.pk).update(uuid=None)
        Formulas.objects.filter(pk=formula.pk).update(uuid=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'legacy_main_bundle.json'
            export_stdout = StringIO()
            import_stdout = StringIO()

            call_command('export_legacy_main_bundle', '--output', str(output_path), stdout=export_stdout)
            payload = json.loads(output_path.read_text(encoding='utf-8'))

            self.assertEqual(payload['category'], 'main')
            self.assertTrue(payload['legacy_source'])

            genres_payload = next(item for item in payload['models'] if item['model'] == 'indexerapp.LiturgicalGenres')
            traditions_payload = next(item for item in payload['models'] if item['model'] == 'indexerapp.Traditions')
            formulas_payload = next(item for item in payload['models'] if item['model'] == 'indexerapp.Formulas')

            expected_genre_uuid = str(build_deterministic_sync_uuid('indexerapp.LiturgicalGenres', genre.pk))
            self.assertEqual(genres_payload['results'][0]['uuid'], expected_genre_uuid)
            self.assertEqual(traditions_payload['results'][0]['genre_uuid'], expected_genre_uuid)
            self.assertEqual(formulas_payload['results'][0]['tradition_uuids'][0], str(build_deterministic_sync_uuid('indexerapp.Traditions', tradition.pk)))

            Formulas.objects.all().delete()
            Traditions.objects.all().delete()
            LiturgicalGenres.objects.all().delete()

            call_command('import_legacy_main_bundle', str(output_path), stdout=import_stdout)

        imported_genre = LiturgicalGenres.objects.get(title='Antiphon')
        imported_tradition = Traditions.objects.get(name='Roman')
        imported_formula = Formulas.objects.get(co_no='CO123')
        self.assertEqual(str(imported_genre.uuid), expected_genre_uuid)
        self.assertIsNotNone(imported_tradition.genre)
        self.assertEqual(imported_tradition.genre, imported_genre)
        self.assertEqual(list(imported_formula.tradition.values_list('pk', flat=True)), [imported_tradition.pk])
        self.assertIn('"created": 3', import_stdout.getvalue())

    def test_serialize_value_converts_decimal_to_string(self):
        payload = {'value': _serialize_value(Decimal('52.123456'))}
        self.assertEqual(payload['value'], '52.123456')
        self.assertEqual(json.dumps(payload), '{"value": "52.123456"}')


class SyncMetadataTests(TestCase):
    def test_shared_model_update_increments_version(self):
        bibliography = Bibliography.objects.create(title='Initial title')

        self.assertEqual(bibliography.version, 1)

        bibliography.title = 'Updated title'
        bibliography.save()
        bibliography.refresh_from_db()

        self.assertEqual(bibliography.version, 2)

    def test_delete_creates_tombstone_record(self):
        bibliography = Bibliography.objects.create(title='Delete me')
        bibliography_uuid = bibliography.uuid

        bibliography.delete()

        tombstone = DeletedRecord.objects.get(model_label='indexerapp.Bibliography', object_uuid=bibliography_uuid)
        self.assertEqual(tombstone.category, 'shared')
        self.assertIsNotNone(tombstone.deleted_at)

    def test_generate_uuids_backfills_missing_values(self):
        bibliography = Bibliography.objects.create(title='Needs UUID', uuid=None)
        Bibliography.objects.filter(pk=bibliography.pk).update(uuid=None)

        call_command('generate_uuids', '--model', 'Bibliography')

        bibliography.refresh_from_db()
        self.assertIsNotNone(bibliography.uuid)

    def test_generate_uuids_can_backfill_deterministically(self):
        bibliography = Bibliography.objects.create(title='Needs deterministic UUID', uuid=None)
        Bibliography.objects.filter(pk=bibliography.pk).update(uuid=None)

        call_command('generate_uuids', '--model', 'Bibliography', '--strategy', 'deterministic')

        bibliography.refresh_from_db()
        self.assertEqual(
            bibliography.uuid,
            build_deterministic_sync_uuid('indexerapp.Bibliography', bibliography.pk),
        )

    def test_validate_uuid_integrity_reports_success(self):
        Bibliography.objects.create(title='Healthy row')
        stdout = StringIO()

        call_command('validate_uuid_integrity', '--model', 'Bibliography', stdout=stdout)

        self.assertIn('status=OK', stdout.getvalue())
        self.assertIn('validation passed', stdout.getvalue().lower())

    def test_validate_uuid_integrity_can_fail_on_missing_values(self):
        bibliography = Bibliography.objects.create(title='Broken row')
        Bibliography.objects.filter(pk=bibliography.pk).update(uuid=None)

        with self.assertRaises(CommandError):
            call_command('validate_uuid_integrity', '--model', 'Bibliography', '--fail-on-issues')

    def test_manuscript_export_and_import_transfers_media_files(self):
        with tempfile.TemporaryDirectory() as source_media_dir, tempfile.TemporaryDirectory() as target_media_dir:
            source_file_path = Path(source_media_dir) / 'images' / 'Kwaternion.jpg'
            source_file_path.parent.mkdir(parents=True, exist_ok=True)
            source_bytes = b'fake-image-content'
            source_file_path.write_bytes(source_bytes)

            with override_settings(MEDIA_ROOT=source_media_dir):
                manuscript = Manuscripts.objects.create(
                    name='Media manuscript',
                    image='images/Kwaternion.jpg',
                )
                payload = build_manuscript_export_payload(manuscript.uuid)

            manuscript_uuid = manuscript.uuid
            Manuscripts.objects.all().delete()

            with override_settings(MEDIA_ROOT=target_media_dir):
                summary = import_manuscript_payload(payload)

            imported_manuscript = Manuscripts.objects.get(uuid=manuscript_uuid)
            imported_file_path = Path(target_media_dir) / 'images' / 'Kwaternion.jpg'

            self.assertEqual(imported_manuscript.image.name, 'images/Kwaternion.jpg')
            self.assertTrue(imported_file_path.exists())
            self.assertEqual(imported_file_path.read_bytes(), source_bytes)
            self.assertEqual(summary['media_summary']['created'], 1)


@override_settings(
    SITE_NAME='Test Site',
    ETL_ROLE='slave',
    ETL_MASTER_URL='http://127.0.0.1:9000',
    ETL_SLAVE_URLS=[],
    ETL_API_TOKEN='test-token',
)
class ETLUIViewTests(ETLUIEditorMixin, TestCase):
    def test_overview_requires_permissions(self):
        user = User.objects.create_user(username='viewer', password='secret123A')
        self.client.force_login(user)

        response = self.client.get(reverse('etl:etl-ui-overview'))

        self.assertEqual(response.status_code, 403)

    @patch('etlapp.views.fetch_remote_etl_json')
    def test_overview_returns_local_and_peer_status(self, fetch_remote_etl_json_mock):
        user = self.create_editor_user()
        self.client.force_login(user)
        fetch_remote_etl_json_mock.return_value = {
            'site_name': 'Master Node',
            'role': 'master',
            'model_category_counts': {'main': 12, 'shared': 8},
        }

        response = self.client.get(reverse('etl:etl-ui-overview'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['local']['site_name'], 'Test Site')
        self.assertEqual(payload['local']['role'], 'slave')
        self.assertEqual(payload['peers'][0]['url'], 'http://127.0.0.1:9000')
        self.assertTrue(payload['peers'][0]['reachable'])
        self.assertEqual(payload['peers'][0]['status']['site_name'], 'Master Node')

    @patch('etlapp.views.fetch_remote_etl_json')
    def test_peer_manuscripts_proxy_returns_remote_payload(self, fetch_remote_etl_json_mock):
        user = self.create_editor_user()
        self.client.force_login(user)
        fetch_remote_etl_json_mock.return_value = {
            'count': 1,
            'results': [{'uuid': str(uuid4()), 'name': 'Remote MS', 'sync_status': 'ready'}],
        }

        response = self.client.get(reverse('etl:etl-ui-manuscripts'), {'peer': 'master'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['peer']['id'], 'master')
        self.assertEqual(payload['payload']['count'], 1)
        self.assertEqual(payload['payload']['results'][0]['name'], 'Remote MS')

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_pull_category_imports_remote_rows_and_applies_deletions(self, fetch_remote_etl_json_mock):
        user = self.create_editor_user()
        self.client.force_login(user)

        deleted_type = Type.objects.create(short_name='DEL', name='Delete me')

        fetch_remote_etl_json_mock.side_effect = [
            {
                'models': [
                    {
                        'model': 'indexerapp.Type',
                        'results': [
                            {
                                'uuid': str(uuid4()),
                                'short_name': 'NEW',
                                'name': 'Imported type',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    }
                ]
            },
            {
                'category': 'main',
                'results': [
                    {
                        'model_label': 'indexerapp.Type',
                        'category': 'main',
                        'object_uuid': str(deleted_type.uuid),
                        'source_pk': str(deleted_type.pk),
                        'deleted_at': timezone.now().isoformat(),
                    }
                ],
            },
        ]

        response = self.client.post(
            reverse('etl:etl-ui-pull-category'),
            data=json.dumps({'peer': 'master', 'category': 'main'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Type.objects.filter(short_name='NEW', name='Imported type').exists())
        self.assertFalse(Type.objects.filter(pk=deleted_type.pk).exists())
        payload = response.json()
        self.assertEqual(payload['result']['import_summary']['created'], 1)
        self.assertEqual(payload['result']['delete_summary']['deleted'], 1)

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_pull_manuscript_imports_remote_package(self, fetch_remote_etl_json_mock):
        user = self.create_editor_user()
        self.client.force_login(user)
        manuscript_uuid = str(uuid4())
        content_uuid = str(uuid4())

        fetch_remote_etl_json_mock.return_value = {
            'models': [
                {
                    'model': 'indexerapp.Manuscripts',
                    'results': [
                        {
                            'uuid': manuscript_uuid,
                            'name': 'Remote manuscript',
                            'sync_status': 'ready',
                            'entry_date': timezone.now().isoformat(),
                        }
                    ],
                },
                {
                    'model': 'indexerapp.Content',
                    'results': [
                        {
                            'uuid': content_uuid,
                            'manuscript_uuid': manuscript_uuid,
                            'formula_text': 'Remote content',
                            'where_in_ms_from': '2r',
                            'entry_date': timezone.now().isoformat(),
                        }
                    ],
                },
            ]
        }

        response = self.client.post(
            reverse('etl:etl-ui-pull-manuscript'),
            data=json.dumps({'peer': 'master', 'manuscript_uuid': manuscript_uuid}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        manuscript = Manuscripts.objects.get(uuid=manuscript_uuid)
        content = Content.objects.get(uuid=content_uuid)
        self.assertEqual(manuscript.name, 'Remote manuscript')
        self.assertEqual(content.manuscript_id, manuscript.pk)
        self.assertEqual(response.json()['result']['import_summary']['created'], 2)

    @patch('etlapp.views.pull_remote_category')
    def test_pull_category_returns_structured_conflict_payload(self, pull_remote_category_mock):
        user = self.create_editor_user()
        self.client.force_login(user)
        pull_remote_category_mock.side_effect = ETLImportConflictError(
            'Shared conflict detected.',
            conflict={
                'reason': 'payload_diff',
                'model': 'indexerapp.Bibliography',
                'object_uuid': str(uuid4()),
                'current_version': 2,
                'incoming_version': 2,
                'local_record': {'title': 'Local'},
                'incoming_record': {'title': 'Remote'},
                'differences': [{'field': 'title', 'local': 'Local', 'incoming': 'Remote'}],
            },
        )

        response = self.client.post(
            reverse('etl:etl-ui-pull-category'),
            data=json.dumps({'peer': 'master', 'category': 'shared'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload['conflict']['model'], 'indexerapp.Bibliography')
        self.assertEqual(payload['conflict']['differences'][0]['field'], 'title')

    def test_resolve_conflict_requires_remote_pull_context(self):
        user = self.create_editor_user()
        self.client.force_login(user)
        bibliography = Bibliography.objects.create(title='Local title')

        response = self.client.post(
            reverse('etl:etl-ui-resolve-conflict'),
            data=json.dumps(
                {
                    'peer': 'master',
                    'category': 'shared',
                    'resolution': 'apply_remote',
                    'conflict': {
                        'model': 'indexerapp.Bibliography',
                        'object_uuid': str(bibliography.uuid),
                        'incoming_record': {
                            'uuid': str(bibliography.uuid),
                            'title': 'Remote title',
                            'author': None,
                            'shortname': None,
                            'year': None,
                            'zotero_id': None,
                            'hierarchy': None,
                            'version': bibliography.version,
                            'entry_date': bibliography.entry_date.isoformat(),
                        },
                    },
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Cannot reach ETL peer', response.json()['detail'])

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_resolve_conflict_applies_remote_version_and_completes_pull(self, fetch_remote_etl_json_mock):
        user = self.create_editor_user()
        self.client.force_login(user)
        bibliography = Bibliography.objects.create(title='Local title')

        fetch_remote_etl_json_mock.side_effect = [
            {
                'models': [
                    {
                        'model': 'indexerapp.Bibliography',
                        'results': [
                            {
                                'uuid': str(bibliography.uuid),
                                'title': 'Remote title',
                                'author': None,
                                'shortname': None,
                                'year': None,
                                'zotero_id': None,
                                'hierarchy': None,
                                'version': bibliography.version,
                                'entry_date': bibliography.entry_date.isoformat(),
                            }
                        ],
                    }
                ]
            },
            {
                'category': 'shared',
                'results': [],
            },
        ]

        response = self.client.post(
            reverse('etl:etl-ui-resolve-conflict'),
            data=json.dumps(
                {
                    'peer': 'master',
                    'category': 'shared',
                    'resolution': 'apply_remote',
                    'conflict': {
                        'model': 'indexerapp.Bibliography',
                        'object_uuid': str(bibliography.uuid),
                        'incoming_record': {
                            'uuid': str(bibliography.uuid),
                            'title': 'Remote title',
                            'author': None,
                            'shortname': None,
                            'year': None,
                            'zotero_id': None,
                            'hierarchy': None,
                            'version': bibliography.version,
                            'entry_date': bibliography.entry_date.isoformat(),
                        },
                    },
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        bibliography.refresh_from_db()
        self.assertEqual(bibliography.title, 'Remote title')
        payload = response.json()
        self.assertTrue(payload['result']['applied'])
        self.assertEqual(payload['result']['pull_result']['import_summary']['updated'], 1)
        self.assertEqual(payload['result']['force_remote_uuids'], [str(bibliography.uuid)])

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_resolve_conflict_keeps_local_version_and_completes_pull(self, fetch_remote_etl_json_mock):
        user = self.create_editor_user()
        self.client.force_login(user)
        bibliography = Bibliography.objects.create(title='Local title')

        fetch_remote_etl_json_mock.side_effect = [
            {
                'models': [
                    {
                        'model': 'indexerapp.Bibliography',
                        'results': [
                            {
                                'uuid': str(bibliography.uuid),
                                'title': 'Remote title',
                                'author': None,
                                'shortname': None,
                                'year': None,
                                'zotero_id': None,
                                'hierarchy': None,
                                'version': bibliography.version,
                                'entry_date': bibliography.entry_date.isoformat(),
                            }
                        ],
                    }
                ]
            },
            {
                'category': 'shared',
                'results': [],
            },
        ]

        response = self.client.post(
            reverse('etl:etl-ui-resolve-conflict'),
            data=json.dumps(
                {
                    'peer': 'master',
                    'category': 'shared',
                    'resolution': 'keep_local',
                    'conflict': {
                        'model': 'indexerapp.Bibliography',
                        'object_uuid': str(bibliography.uuid),
                        'incoming_record': {
                            'uuid': str(bibliography.uuid),
                            'title': 'Remote title',
                            'author': None,
                            'shortname': None,
                            'year': None,
                            'zotero_id': None,
                            'hierarchy': None,
                            'version': bibliography.version,
                            'entry_date': bibliography.entry_date.isoformat(),
                        },
                    },
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        bibliography.refresh_from_db()
        self.assertEqual(bibliography.title, 'Local title')
        payload = response.json()
        self.assertTrue(payload['result']['kept_local'])
        self.assertEqual(payload['result']['pull_result']['import_summary']['skipped'], 1)
        self.assertEqual(payload['result']['keep_local_uuids'], [str(bibliography.uuid)])