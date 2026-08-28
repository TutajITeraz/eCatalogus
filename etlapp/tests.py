import csv
import json
import os
import tempfile
from contextlib import contextmanager
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from etlapp.views import ETLAdminSyncView, ETLUIPullCategoryView, ETLUIPullManuscriptView
from etlapp.main_guard import main_read_only_message, main_read_only_payload, main_writes_allowed
from etlapp.services import ETLImportConflictError, ETLRemoteRequestError, _serialize_value, build_deleted_records_payload, build_delta_export_payload, build_manuscript_export_payload, expand_category_model_selection, get_etl_peer_configs, get_upstream_peer_url, import_delta_payload, import_manuscript_payload, normalize_category_model_selection, pull_remote_category, refresh_category_from_upstream
from etlapp.tasks import get_database_stats
from etlapp.uuid_utils import build_deterministic_sync_uuid
from ecatalogus.env_loader import resolve_runtime_instance_slug
from indexerapp.models import Bibliography, Colours, Content, ContentTopic, Contributors, Day, DeletedRecord, EditionContent, Formulas, LiturgicalGenres, ManuscriptBibliography, ManuscriptGenres, Manuscripts, MassHour, Places, RiteNames, Topic, Traditions, Type, Watermarks


@contextmanager
def _fk_checks_disabled():
    """Lets a test force a stale/dangling FK value that on_delete=PROTECT and the real
    DB constraint would otherwise reject, to simulate data that predates the constraint
    (or arrived via a raw import) for the validators/exporters that are meant to catch it.
    """
    with connection.cursor() as cursor:
        cursor.execute('SET FOREIGN_KEY_CHECKS=0')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SET FOREIGN_KEY_CHECKS=1')


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


class DummyAdminUser:
    pk = 1
    is_authenticated = True
    is_active = True
    is_staff = True
    is_superuser = False

    def get_username(self):
        return 'etl-editor'


class DummyLogEntries(list):
    def filter(self, **kwargs):
        return self


class GetDatabaseStatsTests(SimpleTestCase):
    @override_settings(DATABASES={'default': {'NAME': 'expected_instance_db'}})
    @patch('etlapp.tasks.apps.get_models', return_value=[])
    def test_uses_configured_default_database_name(self, get_models_mock):
        stats = get_database_stats()

        self.assertEqual(stats['database_name'], 'expected_instance_db')
        self.assertEqual(stats['total_records'], 0)


class RuntimeInstanceResolutionTests(SimpleTestCase):
    def test_instance_slug_env_wins(self):
        with patch.dict(os.environ, {'INSTANCE_SLUG': 'corpus-liturgicum'}, clear=False):
            self.assertEqual(resolve_runtime_instance_slug('ecatalogus.settings'), 'corpus-liturgicum')

    def test_service_shortname_fills_missing_instance_slug(self):
        with patch.dict(os.environ, {'INSTANCE_SLUG': '', 'SERVICE_SHORTNAME': 'corpus-liturgicum'}, clear=False):
            self.assertEqual(resolve_runtime_instance_slug('ecatalogus.settings'), 'corpus-liturgicum')

    def test_explicit_instance_settings_module_infers_slug(self):
        with patch.dict(os.environ, {'INSTANCE_SLUG': ''}, clear=False):
            self.assertEqual(resolve_runtime_instance_slug('ecatalogus.settings_corpus-liturgicum'), 'corpus-liturgicum')

    def test_mismatched_instance_slug_and_settings_module_fails(self):
        env_updates = {
            'INSTANCE_SLUG': 'mpl',
            'DJANGO_SETTINGS_MODULE': 'ecatalogus.settings_corpus-liturgicum',
        }
        with patch.dict(os.environ, env_updates, clear=False):
            with self.assertRaises(RuntimeError):
                resolve_runtime_instance_slug()

    def test_generic_settings_module_does_not_guess_from_appdir(self):
        with patch.dict(
            os.environ,
            {'INSTANCE_SLUG': '', 'SERVICE_SHORTNAME': '', 'APPDIR': '/home/deploy/domains/corpus-liturgicum.org/ecatalogus'},
            clear=False,
        ):
            self.assertEqual(resolve_runtime_instance_slug('ecatalogus.settings'), '')


@override_settings(CELERY_TASK_DEFAULT_QUEUE='etl_corpus-liturgicum', ETL_USE_CELERY=True)
class ETLTaskQueueRoutingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_category_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_pull_category_queues_to_current_instance_queue(self, resolve_etl_peer_mock, apply_async_mock, user_can_manage_etl_mock):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        apply_async_mock.return_value.id = 'task-123'
        request = self.factory.post(
            reverse('etl:etl-ui-pull-category'),
            data=json.dumps({'peer': 'peer-1', 'category': 'main'}),
            content_type='application/json',
        )
        request.user = DummyAdminUser()

        response = ETLUIPullCategoryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        apply_async_mock.assert_called_once_with(
            ('http://peer', 'main'),
            {
                'since': None,
                'force_remote_uuids': [],
                'keep_local_uuids': [],
                'models': None,
                'cascade_upstream': False,
            },
            queue='etl_corpus-liturgicum',
        )
        user_can_manage_etl_mock.assert_called_once_with(request.user)

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_manuscript_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_pull_manuscript_queues_to_current_instance_queue(self, resolve_etl_peer_mock, apply_async_mock, user_can_manage_etl_mock):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        manuscript_uuid = str(uuid4())
        apply_async_mock.return_value.id = 'task-456'
        request = self.factory.post(
            reverse('etl:etl-ui-pull-manuscript'),
            data=json.dumps({'peer': 'peer-1', 'manuscript_uuid': manuscript_uuid}),
            content_type='application/json',
        )
        request.user = DummyAdminUser()

        response = ETLUIPullManuscriptView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        apply_async_mock.assert_called_once_with(
            ('http://peer', manuscript_uuid),
            queue='etl_corpus-liturgicum',
        )
        user_can_manage_etl_mock.assert_called_once_with(request.user)


class ETLAdminSyncViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('etlapp.views.user_can_manage_etl', return_value=False)
    def test_admin_sync_view_requires_etl_permissions(self, user_can_manage_etl_mock):
        request = self.factory.get('/admin/etl-sync/')
        request.user = DummyAdminUser()

        with self.assertRaises(PermissionDenied):
            ETLAdminSyncView.as_view()(request)

        user_can_manage_etl_mock.assert_called_once_with(request.user)

    @patch('etlapp.views.admin.site.each_context')
    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    def test_admin_sync_view_renders_for_etl_editor(self, user_can_manage_etl_mock, each_context_mock):
        each_context_mock.return_value = {
            'site_header': 'Manuscript Indexer - Admin',
            'site_title': 'Manuscript Indexer - Admin',
            'site_url': '/',
            'has_permission': True,
            'available_apps': [],
            'is_popup': False,
            'is_nav_sidebar_enabled': True,
            'log_entries': [],
        }
        request = self.factory.get('/admin/etl-sync/')
        request.user = DummyAdminUser()

        response = ETLAdminSyncView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('ETL sync', content)
        self.assertIn('id="etl-peer-select"', content)
        self.assertIn('Open standalone ETL page', content)
        user_can_manage_etl_mock.assert_called_once_with(request.user)
        each_context_mock.assert_called_once_with(request)


class ETLAdminIndexTemplateTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_admin_index_renders_etl_tool_tile(self):
        request = self.factory.get('/admin/')
        request.user = DummyAdminUser()

        rendered = render_to_string(
            'admin/index.html',
            {
                'title': 'Site administration',
                'app_list': [],
                'available_apps': [],
                'is_popup': False,
                'is_nav_sidebar_enabled': True,
                'has_permission': True,
                'log_entries': DummyLogEntries(),
            },
            request=request,
        )

        self.assertIn('/admin/etl-sync/', rendered)
        self.assertIn('ETL tools', rendered)
        self.assertIn('Pull dictionaries and manuscript packages', rendered)


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

    def test_status_endpoint_stays_json_for_html_accept_header(self):
        client = APIClient()

        response = client.get(
            reverse('etl:etl-status'),
            HTTP_AUTHORIZATION='Token test-token',
            HTTP_ACCEPT='text/html',
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['site_name'], 'Test Site')


class ETLRegistryPeerConfigTests(SimpleTestCase):
    def test_registry_peer_config_uses_peer_specific_token_aliases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            registry_path = Path(tmp_dir) / 'instance_registry.toml'
            registry_path.write_text(
                '\n'.join([
                    'version = 1',
                    '',
                    '[instances.ecatalogus]',
                    'slug = "ecatalogus"',
                    'site_name = "eCatalogus"',
                    'public_url = "https://ecatalogus.example.pl"',
                    'role = "master"',
                    'peer_id = "ecatalogus"',
                    'canonical_master = true',
                    '',
                    '[instances.mpl]',
                    'slug = "mpl"',
                    'site_name = "Liturgica Poloniae"',
                    'public_url = "https://mpl.example.pl"',
                    'role = "slave"',
                    'peer_id = "mpl"',
                    'default_parent_peer = "ecatalogus"',
                    'source_peers = ["ecatalogus"]',
                    '',
                    '[instances.limbo]',
                    'slug = "limbo"',
                    'site_name = "MPL Limbo"',
                    'public_url = "https://limbo.example.pl"',
                    'role = "slave"',
                    'peer_id = "limbo"',
                    'default_parent_peer = "mpl"',
                    'source_peers = ["mpl"]',
                ]),
                encoding='utf-8',
            )

            env_updates = {
                'LIMBO_ETL_MPL_API_TOKEN': 'limbo-to-mpl-token',
            }
            with patch.dict(os.environ, env_updates, clear=False):
                with override_settings(
                    ETL_ROLE='slave',
                    ETL_PEER_REGISTRY_PATH=str(registry_path),
                    SETTINGS_MODULE='ecatalogus.settings_limbo',
                    ETL_API_TOKEN='local-limbo-token',
                ):
                    peers = get_etl_peer_configs()

            self.assertEqual(len(peers), 1)
            self.assertEqual(peers[0]['id'], 'mpl')
            self.assertEqual(peers[0]['url'], 'https://mpl.example.pl')
            self.assertEqual(peers[0]['api_token'], 'limbo-to-mpl-token')

    def test_registry_peer_config_does_not_override_parent_peer_specific_token_with_master_alias(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            registry_path = Path(tmp_dir) / 'instance_registry.toml'
            registry_path.write_text(
                '\n'.join([
                    'version = 1',
                    '',
                    '[instances.ecatalogus]',
                    'slug = "ecatalogus"',
                    'site_name = "eCatalogus"',
                    'public_url = "https://ecatalogus.example.pl"',
                    'role = "master"',
                    'peer_id = "ecatalogus"',
                    'canonical_master = true',
                    '',
                    '[instances.mpl]',
                    'slug = "mpl"',
                    'site_name = "Liturgica Poloniae"',
                    'public_url = "https://mpl.example.pl"',
                    'role = "slave"',
                    'peer_id = "mpl"',
                    'default_parent_peer = "ecatalogus"',
                    'source_peers = ["ecatalogus"]',
                    '',
                    '[instances.limbo]',
                    'slug = "limbo"',
                    'site_name = "MPL Limbo"',
                    'public_url = "https://limbo.example.pl"',
                    'role = "slave"',
                    'peer_id = "limbo"',
                    'default_parent_peer = "mpl"',
                    'source_peers = ["mpl"]',
                ]),
                encoding='utf-8',
            )

            env_updates = {
                'ETL_MASTER_API_TOKEN': 'ecatalogus-master-token',
                'LIMBO_TO_MPL_ETL_API_TOKEN': 'limbo-to-mpl-token',
            }
            with patch.dict(os.environ, env_updates, clear=False):
                with override_settings(
                    ETL_ROLE='slave',
                    ETL_PEER_REGISTRY_PATH=str(registry_path),
                    SETTINGS_MODULE='ecatalogus.settings_limbo',
                    ETL_API_TOKEN='local-limbo-token',
                ):
                    peers = get_etl_peer_configs()

            self.assertEqual(len(peers), 1)
            self.assertEqual(peers[0]['id'], 'mpl')
            self.assertEqual(peers[0]['api_token'], 'limbo-to-mpl-token')


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


class ETLUIAsyncFallbackTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_remote_category')
    @patch('etlapp.views.pull_category_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_pull_category_falls_back_to_sync_when_queue_is_unavailable(
        self,
        resolve_etl_peer_mock,
        apply_async_mock,
        pull_remote_category_mock,
        user_can_manage_etl_mock,
    ):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        apply_async_mock.side_effect = RuntimeError('Error 111 connecting to redis')
        pull_remote_category_mock.return_value = {
            'import_summary': {'created': 1, 'updated': 2, 'skipped': 3},
            'delete_summary': {'deleted': 4, 'missing': 5},
        }
        request = self.factory.post(
            reverse('etl:etl-ui-pull-category'),
            data=json.dumps({'peer': 'peer-1', 'category': 'main'}),
            content_type='application/json',
        )
        request.user = DummyAdminUser()

        response = ETLUIPullCategoryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertTrue(payload['async_fallback'])
        self.assertIn('redis', payload['async_error'].lower())
        self.assertEqual(payload['result']['import_summary']['created'], 1)
        pull_remote_category_mock.assert_called_once_with(
            'http://peer',
            'main',
            since=None,
            force_remote_uuids=[],
            keep_local_uuids=[],
            models=None,
            cascade_upstream=False,
        )
        user_can_manage_etl_mock.assert_called_once_with(request.user)

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_remote_manuscript')
    @patch('etlapp.views.pull_manuscript_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_pull_manuscript_falls_back_to_sync_when_queue_is_unavailable(
        self,
        resolve_etl_peer_mock,
        apply_async_mock,
        pull_remote_manuscript_mock,
        user_can_manage_etl_mock,
    ):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        apply_async_mock.side_effect = RuntimeError('Error 111 connecting to redis')
        pull_remote_manuscript_mock.return_value = {
            'import_summary': {'created': 2, 'updated': 1, 'skipped': 0, 'media_summary': {'created': 1}},
        }
        request = self.factory.post(
            reverse('etl:etl-ui-pull-manuscript'),
            data=json.dumps({'peer': 'peer-1', 'manuscript_uuid': str(uuid4())}),
            content_type='application/json',
        )
        request.user = DummyAdminUser()

        response = ETLUIPullManuscriptView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertTrue(payload['async_fallback'])
        self.assertIn('redis', payload['async_error'].lower())
        self.assertEqual(payload['result']['import_summary']['created'], 2)
        user_can_manage_etl_mock.assert_called_once_with(request.user)


@override_settings(ETL_USE_CELERY=False)
class ETLUISynchronousModeTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_remote_category')
    @patch('etlapp.views.pull_category_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_pull_category_runs_sync_when_celery_disabled(
        self,
        resolve_etl_peer_mock,
        apply_async_mock,
        pull_remote_category_mock,
        user_can_manage_etl_mock,
    ):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        pull_remote_category_mock.return_value = {'import_summary': {'created': 1}}
        request = self.factory.post(
            reverse('etl:etl-ui-pull-category'),
            data=json.dumps({'peer': 'peer-1', 'category': 'main'}),
            content_type='application/json',
        )
        request.user = DummyAdminUser()

        response = ETLUIPullCategoryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertFalse(payload['async_fallback'])
        self.assertIsNone(payload['async_error'])
        self.assertEqual(payload['result']['import_summary']['created'], 1)
        apply_async_mock.assert_not_called()
        user_can_manage_etl_mock.assert_called_once_with(request.user)

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_remote_manuscript')
    @patch('etlapp.views.pull_manuscript_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_pull_manuscript_runs_sync_when_celery_disabled(
        self,
        resolve_etl_peer_mock,
        apply_async_mock,
        pull_remote_manuscript_mock,
        user_can_manage_etl_mock,
    ):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        pull_remote_manuscript_mock.return_value = {'import_summary': {'created': 2}}
        request = self.factory.post(
            reverse('etl:etl-ui-pull-manuscript'),
            data=json.dumps({'peer': 'peer-1', 'manuscript_uuid': str(uuid4())}),
            content_type='application/json',
        )
        request.user = DummyAdminUser()

        response = ETLUIPullManuscriptView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertFalse(payload['async_fallback'])
        self.assertIsNone(payload['async_error'])
        self.assertEqual(payload['result']['import_summary']['created'], 2)
        apply_async_mock.assert_not_called()
        user_can_manage_etl_mock.assert_called_once_with(request.user)


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
        self.assertEqual(imported_mass_hour.type_uuid_id, imported_type.uuid)
        self.assertEqual(response.json()['created'], 2)

    def test_main_import_honors_incoming_id_for_stable_id_models(self):
        # RiteNames/Formulas are the two models whose local id is published
        # over the API (apiv1.dictionaries.EXPOSE_LOCAL_ID_SLUGS), so a
        # non-master instance pulling one via ETL must adopt the master's id
        # instead of autoincrementing its own — see
        # etlapp.services.MODELS_WITH_STABLE_ID.
        imported_rite_uuid = str(uuid4())
        imported_type_uuid = str(uuid4())

        client = APIClient()
        response = client.post(
            reverse('etl:etl-delta-import', kwargs={'category': 'main'}),
            {
                'models': [
                    {
                        'model': 'indexerapp.RiteNames',
                        'results': [
                            {
                                'id': 999001,
                                'uuid': imported_rite_uuid,
                                'name': 'Imported Rite',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                    {
                        'model': 'indexerapp.Type',
                        'results': [
                            {
                                'id': 999002,
                                'uuid': imported_type_uuid,
                                'short_name': 'TP2',
                                'name': 'Imported Type 2',
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
        imported_rite = RiteNames.objects.get(uuid=imported_rite_uuid)
        imported_type = Type.objects.get(uuid=imported_type_uuid)
        self.assertEqual(imported_rite.pk, 999001)
        self.assertNotEqual(imported_type.pk, 999002)

    def test_main_import_reorders_models_to_satisfy_m2m_dependencies(self):
        imported_type_uuid = str(uuid4())
        imported_day_uuid = str(uuid4())

        client = APIClient()
        response = client.post(
            reverse('etl:etl-delta-import', kwargs={'category': 'main'}),
            {
                'models': [
                    {
                        'model': 'indexerapp.Day',
                        'results': [
                            {
                                'uuid': imported_day_uuid,
                                'part': 'T',
                                'short_name': 'SUN',
                                'name': 'Sunday',
                                'types_uuids': [imported_type_uuid],
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
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
                ],
            },
            format='json',
            HTTP_AUTHORIZATION='Token test-token',
        )

        self.assertEqual(response.status_code, 200)
        imported_day = Day.objects.get(uuid=imported_day_uuid)
        imported_type = Type.objects.get(uuid=imported_type_uuid)
        self.assertEqual(list(imported_day.types.values_list('uuid', flat=True)), [imported_type.uuid])
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

    def test_shared_import_prefers_m2m_uuid_lists_over_integer_ids(self):
        contributor = Contributors.objects.create(
            initials='AB',
            first_name='Anna',
            last_name='Baker',
        )

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
                                'uuid': str(uuid4()),
                                'name': 'UUID-first watermark',
                                'external_id': None,
                                'watermark_img': None,
                                'comment': 'uuid m2m import',
                                'entry_date': timezone.now().isoformat(),
                                'version': 1,
                                'data_contributor_uuid': str(contributor.uuid),
                                'authors': [],
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
        watermark = Watermarks.objects.get(name='UUID-first watermark')
        self.assertEqual(list(watermark.authors.values_list('pk', flat=True)), [contributor.pk])


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
        exported_content = models_by_label['indexerapp.Content']['results'][0]
        self.assertEqual(exported_content['manuscript_uuid'], str(manuscript.uuid))

    def test_manuscript_export_includes_uuid_foreign_keys_for_main_and_shared_relations(self):
        bibliography = Bibliography.objects.create(title='MS Bibliography')
        genre = LiturgicalGenres.objects.create(title='MS Genre')
        formula = Formulas.objects.create(co_no='CO-MS', text='Formula')
        manuscript = Manuscripts.objects.create(name='MS Export With FK')
        Content.objects.create(manuscript=manuscript, formula=formula, formula_text='Lorem ipsum')
        ManuscriptBibliography.objects.create(manuscript=manuscript, bibliography=bibliography)
        ManuscriptGenres.objects.create(manuscript_uuid=manuscript, genre_uuid=genre)

        payload = build_manuscript_export_payload(manuscript.uuid)
        models_by_label = {model_payload['model']: model_payload for model_payload in payload['models']}

        exported_content = models_by_label['indexerapp.Content']['results'][0]
        exported_manuscript_bibliography = models_by_label['indexerapp.ManuscriptBibliography']['results'][0]
        exported_manuscript_genres = models_by_label['indexerapp.ManuscriptGenres']['results'][0]

        self.assertEqual(exported_content['formula_uuid'], str(formula.uuid))
        self.assertEqual(exported_manuscript_bibliography['bibliography_uuid'], str(bibliography.uuid))
        self.assertEqual(exported_manuscript_genres['manuscript_uuid'], str(manuscript.uuid))
        self.assertEqual(exported_manuscript_genres['genre_uuid'], str(genre.uuid))
        self.assertNotIn('manuscript_uuid_uuid', exported_manuscript_genres)
        self.assertNotIn('genre_uuid_uuid', exported_manuscript_genres)

    def test_manuscript_import_creates_ms_package(self):
        manuscript_uuid = str(uuid4())
        content_uuid = str(uuid4())
        genre_uuid = str(uuid4())
        manuscript_genres_uuid = str(uuid4())
        LiturgicalGenres.objects.create(uuid=genre_uuid, title='Imported liturgical genre')

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
                    {
                        'model': 'indexerapp.ManuscriptGenres',
                        'results': [
                            {
                                'uuid': manuscript_genres_uuid,
                                'manuscript_uuid': manuscript_uuid,
                                'genre_uuid': genre_uuid,
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
        manuscript_genres = ManuscriptGenres.objects.get(uuid=manuscript_genres_uuid)
        self.assertEqual(manuscript.name, 'Imported manuscript')
        self.assertEqual(content.manuscript_uuid_id, manuscript.uuid)
        self.assertEqual(manuscript_genres.manuscript_uuid_id, manuscript.uuid)
        self.assertEqual(str(manuscript_genres.genre_uuid_id), genre_uuid)
        self.assertEqual(response.json()['category'], 'ms')
        self.assertEqual(response.json()['created'], 3)


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

    def test_export_m2m_uuid_plan_writes_sync_many_to_many_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'etl_uuid_m2m_plan.tsv'

            call_command('export_m2m_uuid_plan', output=str(output_path))

            self.assertTrue(output_path.exists())
            with output_path.open('r', encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))

        tradition_m2m = next(
            row for row in rows
            if row['model_name'] == 'Formulas' and row['m2m_field'] == 'tradition'
        )
        self.assertEqual(tradition_m2m['related_model'], 'Traditions')
        self.assertEqual(tradition_m2m['through_auto_created'], 'yes')
        self.assertEqual(tradition_m2m['suggested_uuid_list_key'], 'tradition_uuids')

        authors_m2m = next(
            row for row in rows
            if row['model_name'] == 'Watermarks' and row['m2m_field'] == 'authors'
        )
        self.assertEqual(authors_m2m['related_model'], 'Contributors')
        self.assertEqual(authors_m2m['related_category'], 'shared')

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

    def test_export_etl_bundle_serializes_canonical_uuid_when_relation_target_is_missing(self):
        genre = LiturgicalGenres.objects.create(title='Antiphon')
        tradition = Traditions.objects.create(name='Roman', genre=genre)

        stale_shadow_uuid = uuid4()
        with _fk_checks_disabled():
            Traditions.objects.filter(pk=tradition.pk).update(genre_uuid=stale_shadow_uuid)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'main_bundle.json'

            call_command('export_etl_bundle', '--category', 'main', '--output', str(output_path))
            payload = json.loads(output_path.read_text(encoding='utf-8'))

        traditions_payload = next(item for item in payload['models'] if item['model'] == 'indexerapp.Traditions')
        self.assertEqual(traditions_payload['results'][0]['genre_uuid'], str(stale_shadow_uuid))

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

            expected_genre_uuid = str(genre.uuid)
            expected_tradition_uuid = str(build_deterministic_sync_uuid('indexerapp.Traditions', tradition.pk))
            expected_formula_uuid = str(build_deterministic_sync_uuid('indexerapp.Formulas', formula.pk))
            self.assertEqual(genres_payload['results'][0]['uuid'], expected_genre_uuid)
            self.assertEqual(traditions_payload['results'][0]['genre_uuid'], expected_genre_uuid)
            self.assertEqual(traditions_payload['results'][0]['uuid'], expected_tradition_uuid)
            self.assertEqual(formulas_payload['results'][0]['uuid'], expected_formula_uuid)
            self.assertEqual(formulas_payload['results'][0]['tradition_uuids'][0], expected_tradition_uuid)

            Formulas.objects.all().delete()
            Traditions.objects.all().delete()
            LiturgicalGenres.objects.all().delete()

            call_command('import_legacy_main_bundle', str(output_path), stdout=import_stdout)

        imported_genre = LiturgicalGenres.objects.get(title='Antiphon')
        imported_tradition = Traditions.objects.get(name='Roman')
        imported_formula = Formulas.objects.get(co_no='CO123')
        self.assertEqual(str(imported_genre.uuid), expected_genre_uuid)
        self.assertEqual(str(imported_tradition.uuid), expected_tradition_uuid)
        self.assertEqual(str(imported_formula.uuid), expected_formula_uuid)
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

    def test_shadow_uuid_fk_is_synced_on_save(self):
        type_one = Type.objects.create(short_name='TPA', name='Type A')
        type_two = Type.objects.create(short_name='TPB', name='Type B')

        mass_hour = MassHour.objects.create(short_name='MHA', name='Mass Hour A', type_uuid=type_one)
        self.assertEqual(mass_hour.type_uuid, type_one)
        self.assertEqual(mass_hour.type_uuid_id, type_one.uuid)

        setattr(mass_hour, 'type_uuid_id', type_two.uuid)
        mass_hour.save()
        mass_hour.refresh_from_db()
        self.assertEqual(mass_hour.type_uuid, type_two)
        self.assertEqual(mass_hour.type_uuid_id, type_two.uuid)

        setattr(mass_hour, 'type_uuid_id', None)
        mass_hour.save()
        mass_hour.refresh_from_db()
        self.assertIsNone(mass_hour.type_uuid)

    def test_ms_shadow_uuid_fk_is_synced_on_save(self):
        bibliography = Bibliography.objects.create(title='Shadow bibliography')
        other_bibliography = Bibliography.objects.create(title='Shadow bibliography two')
        manuscript = Manuscripts.objects.create(name='Shadow manuscript')
        relation = ManuscriptBibliography.objects.create(manuscript_uuid=manuscript, bibliography_uuid=bibliography)

        self.assertEqual(relation.bibliography_uuid, bibliography)
        self.assertEqual(relation.bibliography_uuid_id, bibliography.uuid)

        setattr(relation, 'bibliography_uuid_id', other_bibliography.uuid)
        relation.save()
        relation.refresh_from_db()
        self.assertEqual(relation.bibliography_uuid, other_bibliography)
        self.assertEqual(relation.bibliography_uuid_id, other_bibliography.uuid)

    def test_ms_internal_shadow_uuid_fk_is_synced_on_save(self):
        manuscript = Manuscripts.objects.create(name='Source manuscript')
        other_manuscript = Manuscripts.objects.create(name='Other manuscript')
        content = Content.objects.create(manuscript_uuid=manuscript, formula_text='Internal shadow')

        self.assertEqual(content.manuscript_uuid, manuscript)
        self.assertEqual(content.manuscript_uuid_id, manuscript.uuid)

        setattr(content, 'manuscript_uuid_id', other_manuscript.uuid)
        content.save()
        content.refresh_from_db()
        self.assertEqual(content.manuscript_uuid, other_manuscript)
        self.assertEqual(content.manuscript_uuid_id, other_manuscript.uuid)

    def test_populate_uuid_fk_backfills_shadow_columns(self):
        type_one = Type.objects.create(short_name='TPC', name='Type C')
        mass_hour = MassHour.objects.create(short_name='MHC', name='Mass Hour C', type=type_one)
        MassHour.objects.filter(pk=mass_hour.pk).update(type_uuid=None)

        stdout = StringIO()

        call_command('populate_uuid_fk', '--model', 'MassHour', stdout=stdout)

        mass_hour.refresh_from_db()
        self.assertIsNone(mass_hour.type_uuid)
        self.assertIn('MassHour: updated 0 rows', stdout.getvalue())

    def test_validate_uuid_shadow_fks_can_fail_on_mismatch(self):
        type_one = Type.objects.create(short_name='TPD', name='Type D')
        mass_hour = MassHour.objects.create(short_name='MHD', name='Mass Hour D', type=type_one)
        with _fk_checks_disabled():
            MassHour.objects.filter(pk=mass_hour.pk).update(type_uuid=uuid4())

        with self.assertRaises(CommandError):
            call_command('validate_uuid_shadow_fks', '--model', 'MassHour', '--fail-on-issues')

    def test_validate_uuid_shadow_fks_reports_success_after_backfill(self):
        type_one = Type.objects.create(short_name='TPE', name='Type E')
        mass_hour = MassHour.objects.create(short_name='MHE', name='Mass Hour E', type=type_one)
        MassHour.objects.filter(pk=mass_hour.pk).update(type_uuid=None)

        call_command('populate_uuid_fk', '--model', 'MassHour')
        stdout = StringIO()

        call_command('validate_uuid_shadow_fks', '--model', 'MassHour', stdout=stdout)

        self.assertIn('status=OK', stdout.getvalue())
        self.assertIn('validation passed', stdout.getvalue().lower())

    def test_validate_uuid_m2m_reports_success(self):
        contributor = Contributors.objects.create(initials='CD', first_name='Cara', last_name='Doe')
        watermark = Watermarks.objects.create(name='Healthy watermark', data_contributor=contributor)
        watermark.authors.add(contributor)
        stdout = StringIO()

        call_command('validate_uuid_m2m', '--model', 'Watermarks', stdout=stdout)

        self.assertIn('Watermarks.authors: status=OK', stdout.getvalue())
        self.assertIn('validation passed', stdout.getvalue().lower())

    def test_validate_uuid_m2m_can_fail_on_missing_related_uuid(self):
        contributor = Contributors.objects.create(initials='EF', first_name='Evan', last_name='Fox')
        watermark = Watermarks.objects.create(name='Broken watermark', data_contributor=contributor)
        watermark.authors.add(contributor)
        with _fk_checks_disabled():
            Contributors.objects.filter(pk=contributor.pk).update(uuid=None)

        with self.assertRaises(CommandError):
            call_command('validate_uuid_m2m', '--model', 'Watermarks', '--fail-on-issues')

    def test_validate_uuid_transition_readiness_reports_self_reference_without_failing(self):
        colour = Colours.objects.create(name='Self colour', rgb='#123456')
        Colours.objects.filter(pk=colour.pk).update(parent_colour_uuid=colour.uuid)
        stdout = StringIO()

        call_command('validate_uuid_transition_readiness', '--model', 'Colours', stdout=stdout)

        self.assertIn('FK Colours.parent_colour [main]', stdout.getvalue())
        self.assertIn('self_reference=1', stdout.getvalue())
        self.assertIn('validation passed', stdout.getvalue().lower())

    def test_validate_uuid_transition_readiness_can_fail_on_missing_related_uuid(self):
        type_one = Type.objects.create(short_name='TPF', name='Type F')
        mass_hour = MassHour.objects.create(short_name='MHF', name='Mass Hour F', type=type_one)
        with _fk_checks_disabled():
            Type.objects.filter(pk=type_one.pk).update(uuid=None)

        with self.assertRaises(CommandError):
            call_command('validate_uuid_transition_readiness', '--model', 'MassHour', '--fail-on-issues')

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
        self.assertEqual(content.manuscript_uuid_id, manuscript.uuid)
        self.assertEqual(response.json()['result']['import_summary']['created'], 2)

    @patch('indexerapp.management.commands.pull_etl_category.pull_remote_category')
    def test_pull_etl_category_command_returns_json_summary(self, pull_remote_category_mock):
        stdout = StringIO()
        pull_remote_category_mock.return_value = {
            'category': 'main',
            'import_summary': {'created': 1, 'updated': 0, 'skipped': 0},
            'delete_summary': {'deleted': 0, 'missing': 0, 'skipped': 0},
        }

        call_command('pull_etl_category', '--peer', 'master', '--category', 'main', stdout=stdout)

        self.assertIn('"category": "main"', stdout.getvalue())
        self.assertIn('"created": 1', stdout.getvalue())

    @patch('indexerapp.management.commands.pull_etl_manuscript.pull_remote_manuscript')
    def test_pull_etl_manuscript_command_returns_json_summary(self, pull_remote_manuscript_mock):
        stdout = StringIO()
        manuscript_uuid = str(uuid4())
        pull_remote_manuscript_mock.return_value = {
            'manuscript_uuid': manuscript_uuid,
            'import_summary': {'created': 2, 'updated': 0, 'skipped': 0},
        }

        call_command('pull_etl_manuscript', '--peer', 'master', '--manuscript-uuid', manuscript_uuid, stdout=stdout)

        self.assertIn(f'"manuscript_uuid": "{manuscript_uuid}"', stdout.getvalue())
        self.assertIn('"created": 2', stdout.getvalue())

    @patch('indexerapp.management.commands.list_etl_manuscripts.fetch_remote_etl_json')
    def test_list_etl_manuscripts_command_returns_remote_payload(self, fetch_remote_etl_json_mock):
        stdout = StringIO()
        manuscript_uuid = str(uuid4())
        fetch_remote_etl_json_mock.return_value = {
            'count': 1,
            'results': [{'uuid': manuscript_uuid, 'name': 'Remote manuscript'}],
        }

        call_command('list_etl_manuscripts', '--peer', 'master', stdout=stdout)

        self.assertIn('"count": 1', stdout.getvalue())
        self.assertIn(f'"uuid": "{manuscript_uuid}"', stdout.getvalue())

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

def _import_logging_payload(count, name_prefix='Logged'):
    return {
        'category': 'main',
        'models': [
            {
                'model': 'indexerapp.Type',
                'results': [
                    {
                        'uuid': str(uuid4()),
                        'short_name': f'L{index}',
                        'name': f'{name_prefix} {index}',
                        'entry_date': timezone.now().isoformat(),
                    }
                    for index in range(count)
                ],
            }
        ],
    }


class ETLImportLoggingTests(TestCase):
    @override_settings(ETL_IMPORT_LOG_MAX_RECORDS=100)
    def test_small_batch_logs_each_created_record(self):
        payload = _import_logging_payload(3)
        with self.assertLogs('etlapp.import', level='INFO') as captured:
            summary = import_delta_payload('main', payload)

        self.assertEqual(summary['created'], 3)
        self.assertEqual(len(captured.output), 3)
        self.assertIn('indexerapp.Type created uuid=', captured.output[0])
        self.assertEqual(len(summary['models'][0]['created_uuids']), 3)

    @override_settings(ETL_IMPORT_LOG_MAX_RECORDS=2)
    def test_large_batch_collapses_to_one_line_and_omits_uuids(self):
        payload = _import_logging_payload(5)
        with self.assertLogs('etlapp.import', level='INFO') as captured:
            summary = import_delta_payload('main', payload)

        self.assertEqual(len(captured.output), 1)
        self.assertIn('per-record detail suppressed', captured.output[0])
        self.assertNotIn('created_uuids', summary['models'][0])

    @override_settings(ETL_IMPORT_LOG_MAX_RECORDS=100)
    def test_update_logs_changed_field_names(self):
        record_uuid = str(uuid4())
        payload = {
            'category': 'main',
            'models': [
                {
                    'model': 'indexerapp.Type',
                    'results': [
                        {
                            'uuid': record_uuid,
                            'short_name': 'UP1',
                            'name': 'Before',
                            'entry_date': timezone.now().isoformat(),
                        }
                    ],
                }
            ],
        }
        import_delta_payload('main', payload)

        payload['models'][0]['results'][0]['name'] = 'After'
        payload['models'][0]['results'][0]['entry_date'] = timezone.now().isoformat()
        with self.assertLogs('etlapp.import', level='INFO') as captured:
            summary = import_delta_payload('main', payload)

        self.assertEqual(summary['updated'], 1)
        self.assertIn('updated uuid=', captured.output[0])
        self.assertIn('name', captured.output[0])
        self.assertEqual(summary['models'][0]['updated_records'][0]['uuid'], record_uuid)

    @override_settings(ETL_IMPORT_LOG_MAX_RECORDS=100)
    def test_noop_reimport_logs_nothing(self):
        payload = _import_logging_payload(2)
        import_delta_payload('main', payload)

        with self.assertNoLogs('etlapp.import', level='INFO'):
            summary = import_delta_payload('main', payload)

        self.assertEqual(summary['skipped'], 2)

    def test_recent_changes_command_lists_touched_records(self):
        import_delta_payload('main', _import_logging_payload(2, name_prefix='Recent'))

        stdout = StringIO()
        call_command('etl_recent_changes', '--hours', '1', '--model', 'Type', stdout=stdout)
        output = stdout.getvalue()

        self.assertIn('indexerapp.Type [main] - 2 record(s)', output)
        self.assertIn('Recent 0', output)

    def test_recent_changes_command_json_mode(self):
        import_delta_payload('main', _import_logging_payload(1, name_prefix='Json'))

        stdout = StringIO()
        call_command('etl_recent_changes', '--hours', '1', '--model', 'Type', '--json', stdout=stdout)
        report = json.loads(stdout.getvalue())

        self.assertEqual(report['total'], 1)
        self.assertEqual(report['models'][0]['model'], 'indexerapp.Type')


@override_settings(
    SITE_NAME='Liturgica Poloniae',
    ETL_ROLE='slave',
    ETL_SELF_PEER_ID='mpl',
    ETL_CANONICAL_MASTER_ID='ecatalogus',
    ETL_MAIN_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_MASTER_URL='https://ecatalogus.ispan.pl',
)
class MainWritePolicyTests(SimpleTestCase):
    def test_slave_may_not_write_main_locally(self):
        self.assertFalse(main_writes_allowed())

    @override_settings(ETL_SELF_PEER_ID='ecatalogus', ETL_ROLE='master', ETL_MASTER_URL=None)
    def test_canonical_master_may_write_main(self):
        self.assertTrue(main_writes_allowed())

    @override_settings(ETL_ALLOW_MAIN_EDITS=True)
    def test_explicit_override_reopens_editing(self):
        self.assertTrue(main_writes_allowed())

    @override_settings(ETL_SELF_PEER_ID='', INSTANCE_SLUG='')
    def test_instance_without_an_identity_falls_back_to_its_role(self):
        # Single-instance installs and the base settings do not name themselves;
        # only an explicit slave role locks them down.
        self.assertFalse(main_writes_allowed())

        with override_settings(ETL_ROLE='undefined'):
            self.assertTrue(main_writes_allowed())

    def test_refusal_message_names_the_master_and_its_url(self):
        message = main_read_only_message('"Formulas"')

        self.assertIn('"Formulas"', message)
        self.assertIn('https://ecatalogus.ispan.pl', message)

    def test_refusal_payload_carries_the_master_url_for_the_import_ui(self):
        payload = main_read_only_payload('"Rite names"')

        self.assertTrue(payload['read_only'])
        self.assertEqual(payload['main_master_url'], 'https://ecatalogus.ispan.pl')
        self.assertEqual(payload['info'], payload['detail'])


@override_settings(
    SITE_NAME='Liturgica Poloniae',
    ETL_ROLE='slave',
    ETL_SELF_PEER_ID='mpl',
    ETL_CANONICAL_MASTER_ID='ecatalogus',
    ETL_MAIN_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_API_TOKEN='test-token',
)
class MainPullDirectionTests(TestCase):
    @patch('etlapp.services.fetch_remote_etl_json')
    def test_relay_instance_pulls_main_from_its_parent(self, fetch_remote_etl_json_mock):
        # mpl is a slave of eCatalogus and the parent of limbo, so it has to keep
        # receiving main through the ETL even though it may not edit it locally.
        imported_type_uuid = str(uuid4())
        fetch_remote_etl_json_mock.side_effect = [
            {'models': []},
            {'category': 'shared', 'results': []},
            {
                'models': [
                    {
                        'model': 'indexerapp.Type',
                        'results': [
                            {
                                'uuid': imported_type_uuid,
                                'short_name': 'REL',
                                'name': 'Relayed type',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    }
                ]
            },
            {'category': 'main', 'results': []},
        ]

        result = pull_remote_category('https://ecatalogus.ispan.pl', 'main')

        self.assertEqual(result['import_summary']['created'], 1)
        self.assertTrue(Type.objects.filter(uuid=imported_type_uuid).exists())

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_pulling_main_from_a_sibling_is_refused(self, fetch_remote_etl_json_mock):
        with self.assertRaises(ValueError) as raised:
            pull_remote_category('https://limbo.example.pl', 'main')

        self.assertIn('upstream', str(raised.exception))
        self.assertIn('https://ecatalogus.ispan.pl', str(raised.exception))
        fetch_remote_etl_json_mock.assert_not_called()

    @override_settings(ETL_ROLE='master', ETL_SELF_PEER_ID='ecatalogus', ETL_MASTER_URL=None)
    @patch('etlapp.services.fetch_remote_etl_json')
    def test_master_never_pulls_main_from_a_slave(self, fetch_remote_etl_json_mock):
        with self.assertRaises(ValueError) as raised:
            pull_remote_category('https://mpl.example.pl', 'main')

        self.assertIn('curated here', str(raised.exception))
        fetch_remote_etl_json_mock.assert_not_called()

    @override_settings(
        ETL_SELF_PEER_ID='limbo',
        ETL_DEFAULT_PARENT_PEER='mpl',
        ETL_MASTER_URL='https://ecatalogus.ispan.pl',
    )
    @patch('etlapp.services.get_etl_peer_configs')
    @patch('etlapp.services.fetch_remote_etl_json')
    def test_child_pulls_from_its_registry_parent_when_master_url_disagrees(
        self,
        fetch_remote_etl_json_mock,
        get_etl_peer_configs_mock,
    ):
        # limbo's environment still points ETL_MASTER_URL at eCatalogus while the
        # registry makes mpl its parent. mpl is the peer it holds a token for, so
        # the pull has to keep working.
        get_etl_peer_configs_mock.return_value = [{
            'id': 'mpl',
            'label': 'Liturgica Poloniae',
            'url': 'https://monumenta-poloniae-liturgica.ispan.pl',
            'api_token': 'limbo-to-mpl-token',
        }]
        fetch_remote_etl_json_mock.side_effect = [
            {'models': []},
            {'category': 'shared', 'results': []},
            {'models': []},
            {'category': 'main', 'results': []},
        ]

        result = pull_remote_category('https://monumenta-poloniae-liturgica.ispan.pl', 'main')

        self.assertEqual(result['category'], 'main')

    @override_settings(
        ETL_SELF_PEER_ID='limbo',
        ETL_DEFAULT_PARENT_PEER='mpl',
        ETL_MASTER_URL='https://ecatalogus.ispan.pl',
    )
    @patch('etlapp.services.get_etl_peer_configs')
    @patch('etlapp.services.fetch_remote_etl_json')
    def test_sibling_is_still_refused_when_two_upstreams_are_configured(
        self,
        fetch_remote_etl_json_mock,
        get_etl_peer_configs_mock,
    ):
        get_etl_peer_configs_mock.return_value = [{
            'id': 'mpl',
            'label': 'Liturgica Poloniae',
            'url': 'https://monumenta-poloniae-liturgica.ispan.pl',
            'api_token': 'limbo-to-mpl-token',
        }]

        with self.assertRaises(ValueError) as raised:
            pull_remote_category('https://canon-missae.ispan.pl', 'main')

        self.assertIn('upstream', str(raised.exception))
        fetch_remote_etl_json_mock.assert_not_called()

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_shared_pull_is_not_direction_restricted(self, fetch_remote_etl_json_mock):
        # `shared` is bidirectional by design and has its own conflict workflow.
        fetch_remote_etl_json_mock.side_effect = [
            {'models': []},
            {'category': 'shared', 'results': []},
        ]

        result = pull_remote_category('https://limbo.example.pl', 'shared')

        self.assertEqual(result['category'], 'shared')


@override_settings(
    SITE_NAME='Liturgica Poloniae',
    ETL_ROLE='slave',
    ETL_SELF_PEER_ID='mpl',
    ETL_CANONICAL_MASTER_ID='ecatalogus',
    ETL_MAIN_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_API_TOKEN='test-token',
)
class SingleTableSelectionTests(TestCase):
    """Pulling one dictionary table instead of a whole category."""

    def test_selection_accepts_names_labels_and_comma_separated_strings(self):
        self.assertEqual(normalize_category_model_selection('main', ['Places']), ['Places'])
        self.assertEqual(normalize_category_model_selection('main', 'Places,indexerapp.TimeReference'), ['Places', 'TimeReference'])
        self.assertEqual(normalize_category_model_selection('main', 'places'), ['Places'])
        self.assertIsNone(normalize_category_model_selection('main', None))
        self.assertIsNone(normalize_category_model_selection('main', []))

    def test_selection_rejects_a_table_from_another_category(self):
        with self.assertRaises(ValueError) as raised:
            normalize_category_model_selection('main', ['Bibliography'])

        self.assertIn('Bibliography', str(raised.exception))

    def test_selection_carries_same_category_dependencies(self):
        # RiteNames would fail to import without the rows its FKs point at.
        self.assertEqual(
            expand_category_model_selection('main', ['RiteNames']),
            ['Ceremony', 'RiteNames', 'Sections'],
        )
        self.assertEqual(expand_category_model_selection('main', ['Places']), ['Places'])

    def test_export_payload_is_limited_to_the_selected_table(self):
        Places.objects.create(city_today_eng='Kraków')
        Type.objects.create(short_name='T', name='Temporale')

        payload = build_delta_export_payload('main', models=['Places'])

        self.assertEqual(payload['models_filter'], ['Places'])
        self.assertEqual([entry['model'] for entry in payload['models']], ['indexerapp.Places'])
        self.assertEqual(payload['record_count'], 1)

    def test_deleted_records_payload_is_limited_to_the_selected_table(self):
        DeletedRecord.objects.create(
            model_label='indexerapp.Places',
            category='main',
            object_uuid=uuid4(),
            source_pk='1',
        )
        DeletedRecord.objects.create(
            model_label='indexerapp.Type',
            category='main',
            object_uuid=uuid4(),
            source_pk='2',
        )

        payload = build_deleted_records_payload('main', models=['Places'])

        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['model_label'], 'indexerapp.Places')

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_single_table_pull_asks_the_peer_for_that_table_only(self, fetch_remote_etl_json_mock):
        place_uuid = str(uuid4())
        fetch_remote_etl_json_mock.side_effect = [
            {
                'models': [
                    {
                        'model': 'indexerapp.Places',
                        'results': [
                            {
                                'uuid': place_uuid,
                                'city_today_eng': 'Gniezno',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    }
                ]
            },
            {'category': 'main', 'results': []},
        ]

        result = pull_remote_category('https://ecatalogus.ispan.pl', 'main', models=['Places'])

        # Places has no shared references, so the shared preload is skipped and
        # only the two main requests are made.
        self.assertEqual(fetch_remote_etl_json_mock.call_count, 2)
        self.assertIsNone(result['shared_dependency_sync'])
        for call in fetch_remote_etl_json_mock.call_args_list:
            self.assertEqual(call.kwargs['query'], {'models': 'Places'})

        self.assertEqual(result['requested_models'], ['Places'])
        self.assertEqual(result['models'], ['Places'])
        self.assertEqual(result['import_summary']['created'], 1)
        self.assertTrue(Places.objects.filter(uuid=place_uuid).exists())

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_single_table_pull_drops_rows_an_older_peer_kept_sending(self, fetch_remote_etl_json_mock):
        # A peer that does not know the `models` query param answers with the
        # whole category; the selection still has to be honoured locally.
        place_uuid = str(uuid4())
        type_uuid = str(uuid4())
        fetch_remote_etl_json_mock.side_effect = [
            {
                'models': [
                    {
                        'model': 'indexerapp.Places',
                        'results': [
                            {
                                'uuid': place_uuid,
                                'city_today_eng': 'Płock',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                    {
                        'model': 'indexerapp.Type',
                        'results': [
                            {
                                'uuid': type_uuid,
                                'short_name': 'S',
                                'name': 'Sanctorale',
                                'entry_date': timezone.now().isoformat(),
                            }
                        ],
                    },
                ]
            },
            {'category': 'main', 'results': []},
        ]

        result = pull_remote_category('https://ecatalogus.ispan.pl', 'main', models=['Places'])

        self.assertEqual(result['import_summary']['created'], 1)
        self.assertTrue(Places.objects.filter(uuid=place_uuid).exists())
        self.assertFalse(Type.objects.filter(uuid=type_uuid).exists())


@override_settings(ETL_USE_CELERY=True)
class SingleTablePullViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _post(self, body):
        request = self.factory.post(
            reverse('etl:etl-ui-pull-category'),
            data=json.dumps(body),
            content_type='application/json',
        )
        request.user = DummyAdminUser()
        return ETLUIPullCategoryView.as_view()(request)

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_category_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_selected_table_reaches_the_queued_task(self, resolve_etl_peer_mock, apply_async_mock, user_can_manage_etl_mock):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}
        apply_async_mock.return_value.id = 'task-123'

        response = self._post({'peer': 'peer-1', 'category': 'main', 'models': ['Places']})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(apply_async_mock.call_args[0][1]['models'], ['Places'])

    @patch('etlapp.views.user_can_manage_etl', return_value=True)
    @patch('etlapp.views.pull_category_task.apply_async')
    @patch('etlapp.views.resolve_etl_peer')
    def test_unknown_table_is_rejected_before_queueing(self, resolve_etl_peer_mock, apply_async_mock, user_can_manage_etl_mock):
        resolve_etl_peer_mock.return_value = {'id': 'peer-1', 'label': 'Peer 1', 'url': 'http://peer'}

        response = self._post({'peer': 'peer-1', 'category': 'main', 'models': ['Nonexistent']})

        self.assertEqual(response.status_code, 400)
        apply_async_mock.assert_not_called()


@override_settings(
    SITE_NAME='Liturgica Poloniae',
    ETL_ROLE='slave',
    ETL_SELF_PEER_ID='mpl',
    ETL_CANONICAL_MASTER_ID='ecatalogus',
    ETL_MAIN_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_MASTER_URL='https://ecatalogus.ispan.pl',
    # Named explicitly: without it the instance registry on the machine running
    # the tests decides who mpl's parent is.
    ETL_DEFAULT_PARENT_PEER='',
    ETL_API_TOKEN='test-token',
)
class UpstreamRefreshTests(TestCase):
    """A relay catches up with its own master before serving a downstream peer."""

    def _main_export_response(self, type_uuid, name):
        return {
            'models': [
                {
                    'model': 'indexerapp.Type',
                    'results': [
                        {
                            'uuid': type_uuid,
                            'short_name': 'REL',
                            'name': name,
                            'entry_date': timezone.now().isoformat(),
                        }
                    ],
                }
            ]
        }

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_relay_pulls_from_its_master_when_a_downstream_peer_asks(self, fetch_remote_etl_json_mock):
        type_uuid = str(uuid4())
        fetch_remote_etl_json_mock.side_effect = [
            # The master answers the next hop of the cascade: it has no upstream.
            {'category': 'main', 'refreshed': False, 'reason': 'is_source'},
            {'models': []},
            {'category': 'shared', 'results': []},
            self._main_export_response(type_uuid, 'Fresh'),
            {'category': 'main', 'results': []},
        ]

        result = refresh_category_from_upstream('main', requested_by='limbo (127.0.0.1)')

        self.assertTrue(result['refreshed'])
        self.assertEqual(result['upstream_url'], 'https://ecatalogus.ispan.pl')
        self.assertEqual(result['import_summary']['created'], 1)
        self.assertTrue(Type.objects.filter(uuid=type_uuid, name='Fresh').exists())

    @override_settings(ETL_ROLE='master', ETL_SELF_PEER_ID='ecatalogus', ETL_MASTER_URL=None, ETL_DEFAULT_PARENT_PEER='')
    @patch('etlapp.services.fetch_remote_etl_json')
    def test_the_source_instance_reports_that_it_has_no_upstream(self, fetch_remote_etl_json_mock):
        self.assertIsNone(get_upstream_peer_url())

        result = refresh_category_from_upstream('main')

        self.assertFalse(result['refreshed'])
        self.assertEqual(result['reason'], 'is_source')
        fetch_remote_etl_json_mock.assert_not_called()

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_an_unreachable_master_does_not_fail_the_downstream_request(self, fetch_remote_etl_json_mock):
        fetch_remote_etl_json_mock.side_effect = ValueError('Cannot reach ETL peer: timed out')

        result = refresh_category_from_upstream('main')

        self.assertFalse(result['refreshed'])
        self.assertEqual(result['reason'], 'failed')
        self.assertIn('timed out', result['error'])

    @patch('etlapp.services.fetch_remote_etl_json')
    def test_the_selected_table_narrows_the_upstream_refresh_too(self, fetch_remote_etl_json_mock):
        # A one-table pull downstream must stay a one-table pull upstream —
        # otherwise the cascade reintroduces exactly the slow full sync the
        # table selection exists to avoid.
        fetch_remote_etl_json_mock.side_effect = [
            {'category': 'main', 'refreshed': False, 'reason': 'is_source'},
            {'models': []},
            {'category': 'main', 'results': []},
        ]

        refresh_category_from_upstream('main', models=['Places'], since='2025-01-31')

        refresh_calls = [call for call in fetch_remote_etl_json_mock.call_args_list if 'payload' in call.kwargs]
        export_calls = [call for call in fetch_remote_etl_json_mock.call_args_list if call.kwargs.get('query')]

        self.assertEqual(refresh_calls[0].kwargs['payload']['models'], ['Places'])
        self.assertEqual(refresh_calls[0].kwargs['payload']['since'], '2025-01-31')
        self.assertEqual(len(export_calls), 2)
        for call in export_calls:
            self.assertEqual(call.kwargs['query'], {'since': '2025-01-31', 'models': 'Places'})


@override_settings(
    SITE_NAME='Limbo',
    ETL_ROLE='slave',
    ETL_SELF_PEER_ID='limbo',
    ETL_CANONICAL_MASTER_ID='ecatalogus',
    ETL_MAIN_MASTER_URL='https://ecatalogus.ispan.pl',
    ETL_MASTER_URL='https://mpl.example.pl',
    ETL_DEFAULT_PARENT_PEER='',
    ETL_API_TOKEN='test-token',
)
class CascadingPullTests(TestCase):
    """The downstream half: limbo asks mpl to catch up before reading from it."""

    def _peer_responses(self, calls=None, refresh_response=None):
        """Answer whatever the pull asks for, so a test only states what it cares about."""
        def fake_fetch(peer_url, path, **kwargs):
            if calls is not None:
                calls.append((path, kwargs))
            if path.endswith('/refresh-upstream/'):
                if isinstance(refresh_response, Exception):
                    raise refresh_response
                return refresh_response
            category = path.split('/')[3]
            if path.endswith('/deleted/'):
                return {'category': category, 'results': []}
            return {'category': category, 'models': []}

        return fake_fetch

    def test_cascade_asks_the_peer_to_refresh_before_reading_from_it(self):
        calls = []
        fake_fetch = self._peer_responses(
            calls,
            refresh_response={
                'category': 'main',
                'site_name': 'Liturgica Poloniae',
                'upstream_url': 'https://ecatalogus.ispan.pl',
                'refreshed': True,
                'reason': None,
                'error': None,
                'import_summary': {'created': 3, 'updated': 1, 'skipped': 0},
                'delete_summary': {'deleted': 0},
            },
        )

        with patch('etlapp.services.fetch_remote_etl_json', side_effect=fake_fetch):
            result = pull_remote_category(
                'https://mpl.example.pl',
                'main',
                models=['Places'],
                cascade_upstream=True,
            )

        # The refresh has to happen before we read, or we import the stale copy.
        self.assertEqual(calls[0][0], '/api/etl/main/refresh-upstream/')
        self.assertEqual(calls[0][1]['method'], 'POST')
        self.assertEqual(calls[0][1]['payload']['models'], ['Places'])
        self.assertEqual(calls[0][1]['payload']['depth'], 2)
        self.assertTrue(result['upstream_refresh']['refreshed'])
        self.assertEqual(result['upstream_refresh']['import_summary']['created'], 3)

    def test_a_peer_too_old_to_know_the_endpoint_does_not_break_the_pull(self):
        fake_fetch = self._peer_responses(
            refresh_response=ETLRemoteRequestError('Remote ETL request failed (404): Not Found', status_code=404),
        )

        with patch('etlapp.services.fetch_remote_etl_json', side_effect=fake_fetch):
            result = pull_remote_category('https://mpl.example.pl', 'main', cascade_upstream=True)

        self.assertEqual(result['upstream_refresh']['reason'], 'unsupported')
        self.assertFalse(result['upstream_refresh']['refreshed'])
        self.assertEqual(result['import_summary']['created'], 0)

    def test_no_refresh_request_is_sent_when_the_cascade_is_off(self):
        calls = []

        with patch('etlapp.services.fetch_remote_etl_json', side_effect=self._peer_responses(calls)):
            result = pull_remote_category('https://mpl.example.pl', 'main')

        self.assertNotIn('/api/etl/main/refresh-upstream/', [path for path, _ in calls])
        self.assertIsNone(result['upstream_refresh'])

    def test_depth_stops_a_registry_that_names_two_instances_as_each_others_parent(self):
        with patch('etlapp.services.fetch_remote_etl_json', side_effect=self._peer_responses()):
            result = pull_remote_category(
                'https://mpl.example.pl',
                'main',
                cascade_upstream=True,
                cascade_depth=0,
            )

        self.assertEqual(result['upstream_refresh']['reason'], 'depth_exhausted')
        self.assertFalse(result['upstream_refresh']['requested'])


class UpstreamRefreshEndpointTests(TestCase):
    """The HTTP surface a downstream peer talks to."""

    def setUp(self):
        self.client = APIClient()

    @override_settings(ETL_API_TOKEN='test-token')
    @patch('etlapp.views.refresh_category_from_upstream')
    def test_endpoint_forwards_the_request_scope_to_the_service(self, refresh_mock):
        refresh_mock.return_value = {'category': 'main', 'refreshed': True}
        self.client.credentials(HTTP_AUTHORIZATION='Token test-token')

        response = self.client.post(
            reverse('etl:etl-upstream-refresh', args=['main']),
            data={'since': '2025-01-31', 'models': ['Places'], 'depth': 2},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['refreshed'])
        self.assertEqual(refresh_mock.call_args.kwargs['since'], '2025-01-31')
        self.assertEqual(refresh_mock.call_args.kwargs['models'], ['Places'])
        self.assertEqual(refresh_mock.call_args.kwargs['depth'], 2)

    @override_settings(ETL_API_TOKEN='test-token')
    def test_endpoint_rejects_a_category_that_has_no_upstream_flow(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token test-token')

        response = self.client.post(
            reverse('etl:etl-upstream-refresh', args=['ms']),
            data={},
            format='json',
        )

        self.assertEqual(response.status_code, 404)

    def test_endpoint_requires_authentication(self):
        response = self.client.post(
            reverse('etl:etl-upstream-refresh', args=['main']),
            data={},
            format='json',
        )

        self.assertIn(response.status_code, (401, 403))
