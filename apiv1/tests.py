import base64
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from etlapp.uuid_utils import build_deterministic_sync_uuid
from indexerapp.api_access import API_IMPORTER_GROUP
from indexerapp.models import (
    Content,
    ContentFunctions,
    Contributors,
    Formulas,
    LiturgicalGenres,
    ManuscriptMusicNotations,
    Manuscripts,
    MusicNotationNames,
    Places,
    RiteNames,
    ScriptNames,
    Sections,
    TimeReference,
)


def basic_auth(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return f'Basic {token}'


class ApiAccessLockdownTests(TestCase):
    """Regression cover for the endpoints that used to accept anonymous writes."""

    def setUp(self):
        self.manuscript = Manuscripts.objects.create(name='Lockdown MS', display_as_main=True)

    def test_legacy_content_import_rejects_anonymous_post(self):
        response = self.client.post(
            reverse('content_import'),
            data=json.dumps([{'manuscript_uuid': str(self.manuscript.uuid)}]),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Content.objects.count(), 0)

    def test_legacy_manuscripts_import_rejects_anonymous_post(self):
        response = self.client.post(
            reverse('manuscripts_import'),
            data=json.dumps([{'name': 'Injected'}]),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Manuscripts.objects.filter(name='Injected').exists())

    def test_legacy_import_rejects_authenticated_user_without_permission(self):
        user = get_user_model().objects.create_user('nobody', password='Secret123!pass')
        self.client.force_login(user)

        response = self.client.post(
            reverse('content_import'),
            data=json.dumps([{'manuscript_uuid': str(self.manuscript.uuid)}]),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_datatables_viewset_refuses_anonymous_writes_at_the_permission_layer(self):
        """Permissions are checked before method dispatch, so this fails first."""
        create = self.client.post(
            reverse('manuscripts-list'),
            data=json.dumps({'name': 'Injected via viewset'}),
            content_type='application/json',
        )
        self.assertEqual(create.status_code, 403)
        self.assertFalse(Manuscripts.objects.filter(name='Injected via viewset').exists())

        delete = self.client.delete(reverse('manuscripts-detail', kwargs={'pk': self.manuscript.pk}))
        self.assertEqual(delete.status_code, 403)
        self.assertTrue(Manuscripts.objects.filter(pk=self.manuscript.pk).exists())

    def test_datatables_viewset_exposes_no_write_methods_at_all(self):
        """Second, independent layer: the methods do not exist, even for a superuser.

        These viewsets feed read-only UI widgets; editing happens in the Django
        admin and through /api/v1/.
        """
        self.client.force_login(
            get_user_model().objects.create_superuser('vs-admin', 'vs-admin@example.com', 'secret')
        )

        create = self.client.post(
            reverse('manuscripts-list'),
            data=json.dumps({'name': 'Injected via viewset'}),
            content_type='application/json',
        )
        self.assertEqual(create.status_code, 405)
        self.assertFalse(Manuscripts.objects.filter(name='Injected via viewset').exists())

        for method in (self.client.put, self.client.patch, self.client.delete):
            response = method(reverse('manuscripts-detail', kwargs={'pk': self.manuscript.pk}))
            self.assertEqual(response.status_code, 405)

        self.assertTrue(Manuscripts.objects.filter(pk=self.manuscript.pk).exists())

    def test_public_reads_still_work_anonymously(self):
        response = self.client.get(reverse('manuscripts-list'), {'format': 'datatables', 'length': 1})
        self.assertEqual(response.status_code, 200)


class ApiV1ReadTests(TestCase):

    def setUp(self):
        self.place = Places.objects.create(repository_today_eng='Cracow', repository_today_local_language='Krakow')
        self.dating = TimeReference.objects.create(
            time_description='s. XIV in.',
            century_from=14, century_to=14, year_from=1300, year_to=1330,
        )
        self.manuscript = Manuscripts.objects.create(
            name='Missale Cracoviense',
            shelf_mark='MS 1',
            foreign_id='RI-42',
            display_as_main=True,
            contemporary_repository_place_uuid=self.place,
            dating_uuid=self.dating,
        )
        self.rubric = RiteNames.objects.create(name='Ad complendum')
        Content.objects.create(
            manuscript_uuid=self.manuscript,
            rubric_uuid=self.rubric,
            formula_text='Deus qui nos',
            sequence_in_ms=1,
            where_in_ms_from='1r',
        )

    def test_root_lists_endpoints(self):
        response = self.client.get(reverse('apiv1:root'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['api_version'], 'v1')
        self.assertIn('manuscript_content_bulk', payload['endpoints'])

    def test_manuscript_list_is_public_and_carries_labels(self):
        response = self.client.get(reverse('apiv1:manuscript-list'))

        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.json()['results'] if r['uuid'] == str(self.manuscript.uuid))
        self.assertEqual(row['contemporary_repository_place_label'], 'Cracow')
        self.assertEqual(row['dating_label'], 's. XIV in.')
        self.assertEqual(row['content_count'], 1)

    def test_manuscript_list_filters_by_foreign_id(self):
        response = self.client.get(reverse('apiv1:manuscript-list'), {'foreign_id': 'RI-42'})

        self.assertEqual(response.json()['count'], 1)

    def test_package_export_resolves_uuids_to_labels(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        blocks = {block['model']: block for block in payload['models']}
        manuscript_record = blocks['indexerapp.Manuscripts']['results'][0]
        self.assertEqual(manuscript_record['contemporary_repository_place_label'], 'Cracow')
        self.assertEqual(manuscript_record['dating_label'], 's. XIV in.')

    def test_package_export_can_omit_labels(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid}),
            {'labels': 'false'},
        )

        record = next(
            block for block in response.json()['models']
            if block['model'] == 'indexerapp.Manuscripts'
        )['results'][0]
        self.assertNotIn('dating_label', record)

    def test_content_listing_uses_the_import_vocabulary(self):
        response = self.client.get(
            reverse('apiv1:manuscript-content', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        self.assertEqual(response.status_code, 200)
        row = response.json()['results'][0]
        self.assertEqual(row['formula_text_from_ms'], 'Deus qui nos')
        self.assertEqual(row['rubric_id'], str(self.rubric.uuid))
        self.assertEqual(row['rubric_label'], 'Ad complendum')

    def test_content_summary_reports_existing_content(self):
        response = self.client.get(
            reverse('apiv1:manuscript-content-summary', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        payload = response.json()
        self.assertTrue(payload['has_content'])
        self.assertEqual(payload['content_count'], 1)

    def test_unknown_manuscript_returns_404(self):
        response = self.client.get(
            reverse('apiv1:manuscript-content-summary',
                    kwargs={'manuscript_uuid': '0b7622ff-91aa-46c0-a618-124cfc6fca2e'})
        )

        self.assertEqual(response.status_code, 404)

    def test_dictionary_list_and_detail_are_public(self):
        listing = self.client.get(reverse('apiv1:dictionary-list'))
        self.assertEqual(listing.status_code, 200)
        self.assertIn('rite-names', [row['slug'] for row in listing.json()['results']])

        detail = self.client.get(reverse('apiv1:dictionary-detail', kwargs={'slug': 'rite-names'}))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['count'], 1)

    def test_unknown_dictionary_returns_404(self):
        response = self.client.get(reverse('apiv1:dictionary-detail', kwargs={'slug': 'nope'}))
        self.assertEqual(response.status_code, 404)


class ApiV1WriteTests(TestCase):

    def setUp(self):
        self.password = 'Secret123!pass'
        self.importer = get_user_model().objects.create_user('ritus-bot', password=self.password)
        group, _ = Group.objects.get_or_create(name=API_IMPORTER_GROUP)
        self.importer.groups.add(group)

        self.outsider = get_user_model().objects.create_user('outsider', password=self.password)

        self.manuscript = Manuscripts.objects.create(name='Target MS', display_as_main=True)
        self.rubric = RiteNames.objects.create(name='Ad complendum')
        self.genre = LiturgicalGenres.objects.create(title='Missale')
        self.section = Sections.objects.create(name='Ordo Missae')
        self.function = ContentFunctions.objects.create(name='Oratio')
        ScriptNames.objects.create(name='Textualis')
        TimeReference.objects.create(
            time_description='s. XIV in.',
            century_from=14, century_to=14, year_from=1300, year_to=1330,
        )
        Places.objects.create(repository_today_eng='Cracow', repository_today_local_language='Krakow')

    def bulk_url(self):
        return reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': self.manuscript.uuid})

    def post_bulk(self, payload, auth=True):
        headers = {}
        if auth:
            headers['HTTP_AUTHORIZATION'] = basic_auth('ritus-bot', self.password)
        return self.client.post(
            self.bulk_url(),
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    # -- authorisation --------------------------------------------------

    def test_bulk_import_rejects_anonymous(self):
        response = self.post_bulk({'items': [{'formula_text_from_ms': 'x'}]}, auth=False)

        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(Content.objects.count(), 0)

    def test_bulk_import_rejects_account_without_permission(self):
        response = self.client.post(
            self.bulk_url(),
            data=json.dumps({'items': [{'formula_text_from_ms': 'x'}]}),
            content_type='application/json',
            HTTP_AUTHORIZATION=basic_auth('outsider', self.password),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Content.objects.count(), 0)

    def test_model_permission_alone_is_enough(self):
        user = get_user_model().objects.create_user('editor', password=self.password)
        user.user_permissions.add(Permission.objects.get(codename='add_content'))

        response = self.client.post(
            self.bulk_url(),
            data=json.dumps({'items': [{'formula_text_from_ms': 'via model perm'}]}),
            content_type='application/json',
            HTTP_AUTHORIZATION=basic_auth('editor', self.password),
        )

        self.assertEqual(response.status_code, 200)

    # -- import behaviour -----------------------------------------------

    def test_bulk_import_creates_rows_and_resolves_names(self):
        response = self.post_bulk({'items': [
            {
                'formula_text_from_ms': 'Deus qui nos',
                'rubric_id': 'Ad complendum',
                'liturgical_genre_id': 'Missale',
                'section_id': 'Ordo Missae',
                'function_id': 'Oratio',
                'sequence_in_ms': 1,
                'where_in_ms_from': '1r',
            },
            {
                'formula_text_from_ms': 'Per omnia saecula',
                'rubric_id': str(self.rubric.uuid),
                'sequence_in_ms': 2,
                'where_in_ms_from': '1v',
            },
        ]})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload['created'], 2)
        self.assertEqual(payload['received'], 2)
        self.assertEqual(len(payload['created_uuids']), 2)

        first = Content.objects.get(formula_text='Deus qui nos')
        self.assertEqual(first.rubric_uuid, self.rubric)
        self.assertEqual(first.liturgical_genre_uuid, self.genre)
        self.assertEqual(first.section_uuid, self.section)
        self.assertEqual(first.function_uuid, self.function)

    def test_bare_list_body_is_accepted(self):
        response = self.post_bulk([{'formula_text_from_ms': 'bare list'}])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Content.objects.count(), 1)

    def test_bad_row_aborts_the_whole_batch(self):
        response = self.post_bulk({'items': [
            {'formula_text_from_ms': 'good row', 'sequence_in_ms': 1},
            {'formula_text_from_ms': 'bad row', 'rubric_id': 'No Such Rubric'},
            {'formula_text_from_ms': 'another good row', 'sequence_in_ms': 3},
        ]})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(len(payload['errors']), 1)
        self.assertEqual(payload['errors'][0]['row'], 1)
        self.assertEqual(payload['errors'][0]['field'], 'rubric_id')
        self.assertEqual(payload['errors'][0]['error'], 'not_found')
        # Nothing at all was written.
        self.assertEqual(Content.objects.count(), 0)

    def test_unknown_field_is_reported_in_strict_mode(self):
        response = self.post_bulk({'items': [{'formula_text_from_ms': 'x', 'nonsense': 1}]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors'][0]['error'], 'unknown_field')

    def test_unknown_field_is_ignored_when_strict_is_off(self):
        response = self.post_bulk({'items': [{'formula_text_from_ms': 'x', 'nonsense': 1}], 'strict': False})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Content.objects.count(), 1)

    def test_invalid_number_is_reported(self):
        response = self.post_bulk({'items': [{'sequence_in_ms': 'not a number'}]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors'][0]['error'], 'invalid_value')

    def test_dry_run_validates_without_writing(self):
        response = self.post_bulk({
            'items': [{'formula_text_from_ms': 'x', 'rubric_id': 'Ad complendum'}],
            'dry_run': True,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['dry_run'])
        self.assertEqual(response.json()['created'], 0)
        self.assertEqual(Content.objects.count(), 0)

    def test_replace_mode_clears_existing_content(self):
        Content.objects.create(manuscript_uuid=self.manuscript, formula_text='old row')

        response = self.post_bulk({'items': [{'formula_text_from_ms': 'new row'}], 'mode': 'replace'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['deleted'], 1)
        self.assertEqual(
            list(Content.objects.values_list('formula_text', flat=True)),
            ['new row'],
        )

    def test_sequence_is_assigned_when_omitted(self):
        Content.objects.create(manuscript_uuid=self.manuscript, sequence_in_ms=7)

        self.post_bulk({'items': [{'formula_text_from_ms': 'a'}, {'formula_text_from_ms': 'b'}]})

        sequences = sorted(
            Content.objects.exclude(formula_text=None)
            .filter(formula_text__in=['a', 'b'])
            .values_list('sequence_in_ms', flat=True)
        )
        self.assertEqual(sequences, [8, 9])

    def test_empty_batch_is_rejected(self):
        response = self.post_bulk({'items': []})
        self.assertEqual(response.status_code, 400)

    def test_export_output_can_be_reimported_unchanged(self):
        """The round trip that makes this a real interchange format."""
        self.post_bulk({'items': [{
            'formula_text_from_ms': 'Round trip',
            'rubric_id': 'Ad complendum',
            'sequence_in_ms': 1,
            'where_in_ms_from': '2r',
        }]})

        exported = self.client.get(
            reverse('apiv1:manuscript-content', kwargs={'manuscript_uuid': self.manuscript.uuid})
        ).json()['results']

        other = Manuscripts.objects.create(name='Copy target', display_as_main=True)
        response = self.client.post(
            reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': other.uuid}),
            data=json.dumps({'items': exported}),
            content_type='application/json',
            HTTP_AUTHORIZATION=basic_auth('ritus-bot', self.password),
        )

        self.assertEqual(response.status_code, 200, response.content)
        copied = Content.objects.get(manuscript_uuid=other)
        self.assertEqual(copied.formula_text, 'Round trip')
        self.assertEqual(copied.rubric_uuid, self.rubric)
        self.assertEqual(copied.where_in_ms_from, '2r')


class ApiV1ManuscriptCreationTests(TestCase):

    def setUp(self):
        self.password = 'Secret123!pass'
        self.importer = get_user_model().objects.create_user('ritus-bot', password=self.password)
        group, _ = Group.objects.get_or_create(name=API_IMPORTER_GROUP)
        self.importer.groups.add(group)

        Places.objects.create(repository_today_eng='Cracow', repository_today_local_language='Krakow')
        TimeReference.objects.create(
            time_description='s. XIV in.',
            century_from=14, century_to=14, year_from=1300, year_to=1330,
        )
        ScriptNames.objects.create(name='Textualis')

    def post(self, payload, auth=True):
        headers = {}
        if auth:
            headers['HTTP_AUTHORIZATION'] = basic_auth('ritus-bot', self.password)
        return self.client.post(
            reverse('apiv1:manuscript-list'),
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    def test_anonymous_cannot_create(self):
        response = self.post({'name': 'Sneaky'}, auth=False)

        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Manuscripts.objects.filter(name='Sneaky').exists())

    def test_creates_manuscript_with_named_relations(self):
        response = self.post({
            'name': 'Graduale Cracoviense',
            'foreign_id': 'RI-77',
            'shelf_mark': 'MS 12',
            'contemporary_repository_place': 'Krakow',
            'dating': 's. XIV in.',
            'main_script': 'Textualis',
        })

        self.assertEqual(response.status_code, 201, response.content)
        manuscript = Manuscripts.objects.get(name='Graduale Cracoviense')
        self.assertEqual(response.json()['uuid'], str(manuscript.uuid))
        self.assertEqual(manuscript.dating_uuid.time_description, 's. XIV in.')
        self.assertEqual(manuscript.main_script_uuid.name, 'Textualis')
        # Must be visible to the content endpoints, which filter on this flag.
        self.assertTrue(manuscript.display_as_main)

    def test_missing_name_is_rejected(self):
        response = self.post({'shelf_mark': 'MS 13'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors'][0]['field'], 'name')

    def test_unknown_dictionary_value_is_rejected_not_created(self):
        response = self.post({'name': 'Bad dating', 'dating': 's. XXX'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors'][0]['error'], 'not_found')
        self.assertFalse(Manuscripts.objects.filter(name='Bad dating').exists())
        self.assertEqual(TimeReference.objects.count(), 1)


class ApiThrottlingTests(TestCase):
    """The promise made in INTEGRATION.md: anonymous is capped, authenticated is not."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.password = 'Secret123!pass'
        user = get_user_model().objects.create_user('ritus-bot', password=self.password)
        group, _ = Group.objects.get_or_create(name=API_IMPORTER_GROUP)
        user.groups.add(group)

        self.manuscript = Manuscripts.objects.create(name='Throttled MS', display_as_main=True)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    @staticmethod
    def _rates(anon):
        # DRF binds THROTTLE_RATES onto the throttle class at import time, so
        # override_settings does not reach it — patch the class directly.
        from unittest import mock

        from rest_framework.throttling import AnonRateThrottle

        return mock.patch.object(
            AnonRateThrottle,
            'THROTTLE_RATES',
            dict(AnonRateThrottle.THROTTLE_RATES, anon=anon),
        )

    def test_anonymous_reads_are_throttled(self):
        with self._rates('2/min'):
            statuses = [
                self.client.get(reverse('apiv1:manuscript-list')).status_code
                for _ in range(4)
            ]

        self.assertIn(429, statuses)

    def test_authenticated_reads_are_never_throttled(self):
        with self._rates('2/min'):
            statuses = [
                self.client.get(
                    reverse('apiv1:manuscript-list'),
                    HTTP_AUTHORIZATION=basic_auth('ritus-bot', self.password),
                ).status_code
                for _ in range(6)
            ]

        self.assertEqual(set(statuses), {200})

    def test_bulk_import_is_never_throttled(self):
        url = reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': self.manuscript.uuid})

        with self._rates('1/min'):
            statuses = [
                self.client.post(
                    url,
                    data=json.dumps({'items': [{'formula_text_from_ms': f'row {n}'}]}),
                    content_type='application/json',
                    HTTP_AUTHORIZATION=basic_auth('ritus-bot', self.password),
                ).status_code
                for n in range(5)
            ]

        self.assertEqual(set(statuses), {200})
        self.assertEqual(Content.objects.count(), 5)


class ApiSchemaTests(TestCase):

    def test_schema_is_publicly_reachable(self):
        """Integration partners need the reference without an admin account."""
        response = self.client.get(reverse('api-schema'))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('/api/v1/manuscripts/{manuscript_uuid}/content/bulk/', body)

    def test_swagger_ui_is_publicly_reachable(self):
        response = self.client.get(reverse('api-schema-swagger'))

        self.assertEqual(response.status_code, 200)


class BrowserIntegrationTests(TestCase):
    """The ritus-indexer flow: partner-site JavaScript, credentials typed by the user."""

    PARTNER_ORIGIN = 'https://ritus-indexer.ispan.pl'

    def setUp(self):
        self.password = 'Secret123!pass'
        self.importer = get_user_model().objects.create_user(
            'historyk', password=self.password, first_name='Anna', last_name='Kowalska',
        )
        group, _ = Group.objects.get_or_create(name=API_IMPORTER_GROUP)
        self.importer.groups.add(group)

        self.outsider = get_user_model().objects.create_user('gosc', password=self.password)
        self.manuscript = Manuscripts.objects.create(name='Browser MS', display_as_main=True)

    # -- who am I -------------------------------------------------------

    def test_whoami_confirms_identity_and_import_right(self):
        response = self.client.get(
            reverse('apiv1:whoami'),
            HTTP_AUTHORIZATION=basic_auth('historyk', self.password),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['authenticated'])
        self.assertEqual(payload['username'], 'historyk')
        self.assertEqual(payload['display_name'], 'Anna Kowalska')
        self.assertTrue(payload['can_import'])

    def test_whoami_separates_wrong_password_from_missing_rights(self):
        wrong_password = self.client.get(
            reverse('apiv1:whoami'),
            HTTP_AUTHORIZATION=basic_auth('historyk', 'not-my-password'),
        )
        self.assertEqual(wrong_password.status_code, 401)

        no_rights = self.client.get(
            reverse('apiv1:whoami'),
            HTTP_AUTHORIZATION=basic_auth('gosc', self.password),
        )
        self.assertEqual(no_rights.status_code, 200)
        self.assertTrue(no_rights.json()['authenticated'])
        self.assertFalse(no_rights.json()['can_import'])

    def test_whoami_is_answerable_anonymously(self):
        response = self.client.get(reverse('apiv1:whoami'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['authenticated'])
        self.assertFalse(response.json()['can_import'])

    # -- no native browser password dialog -------------------------------

    def test_failed_auth_does_not_trigger_the_browser_login_popup(self):
        response = self.client.get(
            reverse('apiv1:whoami'),
            HTTP_AUTHORIZATION=basic_auth('historyk', 'wrong'),
        )

        self.assertEqual(response.status_code, 401)
        # A 'Basic ...' challenge would make the browser render its own dialog
        # on top of the partner site's form.
        self.assertFalse(response.get('WWW-Authenticate', '').startswith('Basic'))

    # -- CORS ------------------------------------------------------------

    def test_preflight_from_partner_origin_is_allowed(self):
        response = self.client.options(
            reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': self.manuscript.uuid}),
            HTTP_ORIGIN=self.PARTNER_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization,content-type',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Access-Control-Allow-Origin'], self.PARTNER_ORIGIN)
        self.assertIn('authorization', response['Access-Control-Allow-Headers'].lower())

    def test_actual_request_from_partner_origin_carries_cors_headers(self):
        response = self.client.post(
            reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': self.manuscript.uuid}),
            data=json.dumps({'items': [{'formula_text_from_ms': 'from the browser'}]}),
            content_type='application/json',
            HTTP_ORIGIN=self.PARTNER_ORIGIN,
            HTTP_AUTHORIZATION=basic_auth('historyk', self.password),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response['Access-Control-Allow-Origin'], self.PARTNER_ORIGIN)
        self.assertEqual(Content.objects.count(), 1)

    def test_unknown_origin_is_not_granted_cors_access(self):
        response = self.client.get(
            reverse('apiv1:whoami'),
            HTTP_ORIGIN='https://evil.example.com',
        )

        self.assertNotIn('Access-Control-Allow-Origin', response)

    # -- same-origin session still works ---------------------------------

    def test_session_login_can_import_without_basic_auth(self):
        self.client.force_login(self.importer)

        response = self.client.post(
            reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': self.manuscript.uuid}),
            data=json.dumps({'items': [{'formula_text_from_ms': 'from a session'}]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Content.objects.count(), 1)


class DataLicensingTests(TestCase):
    """Every export must say who owns the data, who made it, and on what terms."""

    def setUp(self):
        self.anna = Contributors.objects.create(
            initials='AK', first_name='Anna', last_name='Kowalska',
            affiliation='Instytut Sztuki PAN',
        )
        self.jan = Contributors.objects.create(
            initials='JN', first_name='Jan', last_name='Nowak',
            affiliation='Uniwersytet Warszawski',
        )
        self.manuscript = Manuscripts.objects.create(
            name='Graduale Cracoviense',
            display_as_main=True,
            data_contributor_uuid=self.anna,
        )
        content = Content.objects.create(
            manuscript_uuid=self.manuscript,
            formula_text='Deus qui nos',
            data_contributor_uuid=self.jan,
        )
        content.authors.add(self.jan)

    def test_license_link_header_on_every_v1_response(self):
        for name, kwargs in [
            ('apiv1:root', {}),
            ('apiv1:manuscript-list', {}),
            ('apiv1:dictionary-list', {}),
        ]:
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertIn('rel="license"', response['Link'], name)
            self.assertIn('creativecommons.org', response['Link'], name)

    def test_license_link_header_present_even_on_errors(self):
        response = self.client.get(reverse('apiv1:dictionary-detail', kwargs={'slug': 'nope'}))

        self.assertEqual(response.status_code, 404)
        self.assertIn('rel="license"', response['Link'])

    def test_package_export_states_copyright_and_licence(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        rights = response.json()['rights']
        self.assertEqual(rights['license'], 'CC-BY-4.0')
        self.assertIn('Instytut Sztuki Polskiej Akademii Nauk', rights['copyright'])
        self.assertIn('2024-2026', rights['copyright'])
        self.assertTrue(rights['license_url'].startswith('https://creativecommons.org/'))
        self.assertEqual(rights['rights_holder'], 'Instytut Sztuki Polskiej Akademii Nauk (PAN)')

    def test_package_export_credits_the_people_in_the_export(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        rights = response.json()['rights']
        names = [person['name'] for person in rights['contributors']]
        self.assertIn('Anna Kowalska', names)   # manuscript data contributor
        self.assertIn('Jan Nowak', names)       # content author / contributor

        affiliations = {p['name']: p['affiliation'] for p in rights['contributors']}
        self.assertEqual(affiliations['Anna Kowalska'], 'Instytut Sztuki PAN')

        self.assertIn('Anna Kowalska', rights['attribution'])
        self.assertIn('Graduale Cracoviense', rights['attribution'])

    def test_recommended_citation_is_ready_to_paste(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        citation = response.json()['rights']['recommended_citation']
        self.assertIn('Graduale Cracoviense', citation)
        self.assertIn('CC-BY-4.0', citation)
        self.assertIn('accessed', citation)
        self.assertTrue(citation.endswith('.'))

    def test_rights_travel_with_content_and_dictionaries_too(self):
        for url in [
            reverse('apiv1:manuscript-content', kwargs={'manuscript_uuid': self.manuscript.uuid}),
            reverse('apiv1:manuscript-content-summary', kwargs={'manuscript_uuid': self.manuscript.uuid}),
            reverse('apiv1:dictionary-detail', kwargs={'slug': 'rite-names'}),
            reverse('apiv1:manuscript-list'),
        ]:
            payload = self.client.get(url).json()
            self.assertIn('rights', payload, url)
            self.assertEqual(payload['rights']['license'], 'CC-BY-4.0', url)

    def test_source_url_is_recorded_so_the_export_is_traceable(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        rights = response.json()['rights']
        self.assertIn(str(self.manuscript.uuid), rights['source'])
        self.assertIsNotNone(rights['accessed'])

    def test_tei_export_carries_the_licence(self):
        response = self.client.get(reverse('manuscript_tei_xml'),
                                   {'manuscript_uuid': str(self.manuscript.uuid)})

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('<availability', body)
        self.assertIn('creativecommons.org', body)
        self.assertIn('Instytut Sztuki Polskiej Akademii Nauk', body)
        self.assertIn('rel="license"', response['Link'])


class GrantApiAccessCommandTests(TestCase):
    """The command must never damage an existing account it is pointed at."""

    def run_command(self, *args, **kwargs):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('create_api_integration_user', *args, stdout=out, **kwargs)
        return out.getvalue()

    def test_creates_the_group_so_it_is_selectable_in_the_admin(self):
        Group.objects.filter(name=API_IMPORTER_GROUP).delete()

        self.run_command('fresh-bot')

        self.assertTrue(Group.objects.filter(name=API_IMPORTER_GROUP).exists())

    def test_grants_access_to_an_existing_user_without_touching_anything_else(self):
        user = get_user_model().objects.create_user('akowalska', password='Original!pass1')
        user.is_staff = True
        user.is_superuser = True
        user.save()

        self.run_command('akowalska')

        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name=API_IMPORTER_GROUP).exists())
        # The three things that must survive.
        self.assertTrue(user.check_password('Original!pass1'))
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_new_account_gets_no_admin_rights(self):
        self.run_command('ritus-bot', password='Bot!pass123')

        user = get_user_model().objects.get(username='ritus-bot')
        self.assertTrue(user.check_password('Bot!pass123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.groups.filter(name=API_IMPORTER_GROUP).exists())

    def test_password_is_reset_only_when_explicitly_asked(self):
        get_user_model().objects.create_user('akowalska', password='Original!pass1')

        self.run_command('akowalska', password='Rotated!pass1')

        user = get_user_model().objects.get(username='akowalska')
        self.assertTrue(user.check_password('Rotated!pass1'))

    def test_remove_revokes_access_but_keeps_the_account(self):
        user = get_user_model().objects.create_user('akowalska', password='Original!pass1')
        self.run_command('akowalska')

        self.run_command('akowalska', remove=True)

        user.refresh_from_db()
        self.assertFalse(user.groups.filter(name=API_IMPORTER_GROUP).exists())
        self.assertTrue(get_user_model().objects.filter(username='akowalska').exists())
        self.assertTrue(user.check_password('Original!pass1'))


class DictionarySelectorTests(TestCase):
    """The ``?uuids=`` / ``?legacy_ids=`` / ``?fields=`` selectors, and the
    deliberate absence of the local ``id`` column."""

    def setUp(self):
        self.rubric = RiteNames.objects.create(name='Ad complendum')
        self.other = RiteNames.objects.create(name='Ad populum')
        self.manuscript = Manuscripts.objects.create(name='Target MS', display_as_main=True)

    def dictionary(self, params=None, slug='rite-names'):
        return self.client.get(
            reverse('apiv1:dictionary-detail', kwargs={'slug': slug}), params or {}
        )

    def test_local_id_is_not_published(self):
        # Each instance numbers its own rows, so publishing `id` next to `uuid`
        # invites a caller to key on a value that means something else elsewhere.
        # rite-names/formulas are the deliberate exception — see the next test.
        Sections.objects.create(name='Test Section')
        response = self.dictionary(slug='sections')

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['results'])
        for record in payload['results']:
            self.assertNotIn('id', record)
            self.assertIn('uuid', record)

    def test_rite_names_and_formulas_publish_local_id(self):
        # These two are `main`-category vocabularies: etlapp.main_guard blocks
        # local edits everywhere but the canonical master, and
        # etlapp.services.MODELS_WITH_STABLE_ID keeps their id identical across
        # instances, so publishing it here doesn't reintroduce the drift risk.
        formula = Formulas.objects.create(co_no='Formula co_no')

        response = self.dictionary(slug='rite-names')
        self.assertEqual(response.status_code, 200)
        by_uuid = {record['uuid']: record for record in response.json()['results']}
        self.assertEqual(by_uuid[str(self.rubric.uuid)]['id'], self.rubric.pk)
        self.assertEqual(by_uuid[str(self.other.uuid)]['id'], self.other.pk)

        response = self.dictionary(slug='formulas')
        self.assertEqual(response.status_code, 200)
        by_uuid = {record['uuid']: record for record in response.json()['results']}
        self.assertEqual(by_uuid[str(formula.uuid)]['id'], formula.pk)

    def test_package_does_not_publish_local_ids_either(self):
        response = self.client.get(
            reverse('apiv1:manuscript-package', kwargs={'manuscript_uuid': self.manuscript.uuid})
        )

        self.assertEqual(response.status_code, 200)
        for block in response.json()['models']:
            for record in block['results']:
                self.assertNotIn('id', record)

    def test_selects_named_uuids_only(self):
        response = self.dictionary({'uuids': str(self.rubric.uuid)})

        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['uuid'], str(self.rubric.uuid))

    def test_malformed_uuid_is_a_bad_request_not_an_empty_page(self):
        response = self.dictionary({'uuids': f'{self.rubric.uuid},not-a-uuid'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('not-a-uuid', response.json()['detail'])

    def test_resolves_legacy_ids_and_names_the_ones_it_cannot(self):
        migrated = RiteNames.objects.create(name='Ad missam')
        RiteNames.objects.filter(pk=migrated.pk).update(
            uuid=build_deterministic_sync_uuid('indexerapp.RiteNames', 4242)
        )

        response = self.dictionary({'legacy_ids': '4242,999999'})

        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['name'], 'Ad missam')
        self.assertEqual(payload['results'][0]['legacy_id'], 4242)
        self.assertEqual(payload['unresolved_legacy_ids'], [999999])

    def test_legacy_ids_rejects_non_numeric_values(self):
        response = self.dictionary({'legacy_ids': '1,abc'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('abc', response.json()['detail'])

    def test_fields_projection_always_keeps_uuid(self):
        response = self.dictionary({'fields': 'name'})

        record = response.json()['results'][0]
        # rite-names also always keeps `id` — see
        # test_rite_names_and_formulas_publish_local_id.
        self.assertEqual(sorted(record), ['id', 'name', 'uuid'])

    def test_unknown_query_parameter_is_rejected(self):
        # Answering 200 to ?ids=1 is how a caller convinces itself that a filter
        # it invented is being applied.
        response = self.dictionary({'ids': '1'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('ids', response.json()['detail'])

    def test_documented_parameters_are_still_accepted(self):
        response = self.dictionary({'search': 'complend', 'limit': 10, 'offset': 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)


class MusicNotationImportTests(TestCase):
    """``music_notation_id`` points at one manuscript's notation record, so a
    notation *name* can only be resolved within the manuscript being imported."""

    def setUp(self):
        self.password = 'Secret123!pass'
        self.importer = get_user_model().objects.create_user('ritus-bot', password=self.password)
        group, _ = Group.objects.get_or_create(name=API_IMPORTER_GROUP)
        self.importer.groups.add(group)

        self.manuscript = Manuscripts.objects.create(name='Notated MS', display_as_main=True)
        self.bare = Manuscripts.objects.create(name='Unnotated MS', display_as_main=True)
        self.square = MusicNotationNames.objects.create(name='Square notation')
        self.block = ManuscriptMusicNotations.objects.create(
            manuscript_uuid=self.manuscript,
            music_notation_name_uuid=self.square,
            sequence_in_ms=1,
            where_in_ms_from='1r',
        )

    def post_bulk(self, manuscript, payload):
        return self.client.post(
            reverse('apiv1:manuscript-content-bulk', kwargs={'manuscript_uuid': manuscript.uuid}),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=basic_auth('ritus-bot', self.password),
        )

    def test_notation_name_resolves_to_this_manuscripts_record(self):
        response = self.post_bulk(self.manuscript, {
            'items': [{'formula_text_from_ms': 'Deus qui nos', 'music_notation_id': 'Square notation'}],
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Content.objects.get().music_notation_uuid_id, self.block.uuid)

    def test_notation_name_is_case_insensitive(self):
        response = self.post_bulk(self.manuscript, {
            'items': [{'formula_text_from_ms': 'x', 'music_notation_id': 'square NOTATION'}],
        })

        self.assertEqual(response.status_code, 200, response.content)

    def test_known_notation_the_manuscript_does_not_use_is_reported_precisely(self):
        response = self.post_bulk(self.bare, {
            'items': [{'formula_text_from_ms': 'x', 'music_notation_id': 'Square notation'}],
        })

        self.assertEqual(response.status_code, 400)
        error = response.json()['errors'][0]
        self.assertEqual(error['field'], 'music_notation_id')
        self.assertIn('Unnotated MS', error['detail'])
        self.assertEqual(Content.objects.count(), 0)

    def test_unknown_notation_name_is_rejected(self):
        response = self.post_bulk(self.manuscript, {
            'items': [{'formula_text_from_ms': 'x', 'music_notation_id': 'Cistercian neumes'}],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Content.objects.count(), 0)

    def test_notation_record_uuid_still_works(self):
        response = self.post_bulk(self.manuscript, {
            'items': [{'formula_text_from_ms': 'x', 'music_notation_id': str(self.block.uuid)}],
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Content.objects.get().music_notation_uuid_id, self.block.uuid)
