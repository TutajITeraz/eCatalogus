import json
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse

from indexerapp.models import Content, Formulas, Hands, Image, Layouts, LiturgicalGenres, MSProjects, ManuscriptGenres, ManuscriptHands, Manuscripts, Projects, RiteNames, ScriptNames, Traditions
from indexerapp.signals import ensure_env_superuser


class EnvSuperuserBootstrapTests(TestCase):
	def test_ensure_env_superuser_creates_missing_superuser(self):
		with patch.dict(
			'os.environ',
			{
				'DJANGO_SUPERUSER_USERNAME': 'env-admin',
				'DJANGO_SUPERUSER_EMAIL': 'env-admin@example.com',
				'DJANGO_SUPERUSER_PASSWORD': 'Secret123!pass',
			},
			clear=False,
		):
			changed = ensure_env_superuser()

		user_model = get_user_model()
		user = user_model.objects.get(username='env-admin')
		self.assertTrue(changed)
		self.assertTrue(user.is_superuser)
		self.assertTrue(user.is_staff)
		self.assertEqual(user.email, 'env-admin@example.com')
		self.assertTrue(user.check_password('Secret123!pass'))

	def test_ensure_env_superuser_repairs_existing_user_flags_and_password(self):
		user_model = get_user_model()
		user = user_model.objects.create_user(
			username='env-admin',
			email='old@example.com',
			password='old-pass',
		)
		user.is_staff = False
		user.is_superuser = False
		user.save(update_fields=['is_staff', 'is_superuser'])

		with patch.dict(
			'os.environ',
			{
				'DJANGO_SUPERUSER_USERNAME': 'env-admin',
				'DJANGO_SUPERUSER_EMAIL': 'new@example.com',
				'DJANGO_SUPERUSER_PASSWORD': 'NewSecret123!',
			},
			clear=False,
		):
			changed = ensure_env_superuser()

		user.refresh_from_db()
		self.assertTrue(changed)
		self.assertTrue(user.is_superuser)
		self.assertTrue(user.is_staff)
		self.assertEqual(user.email, 'new@example.com')
		self.assertTrue(user.check_password('NewSecret123!'))


class AdminUUIDVisibilityTests(TestCase):
	def test_content_admin_exposes_uuid(self):
		content_admin = admin.site._registry[Content]
		self.assertIn('uuid', tuple(content_admin.list_display))
		self.assertIn('uuid', tuple(content_admin.readonly_fields))

	def test_manuscripts_admin_keeps_uuid_visible(self):
		manuscripts_admin = admin.site._registry[Manuscripts]
		self.assertIn('uuid', tuple(manuscripts_admin.list_display))
		self.assertIn('uuid', tuple(manuscripts_admin.readonly_fields))

	def test_layout_admin_form_uses_uuid_for_manuscript_field(self):
		request = RequestFactory().get('/admin/')
		request.user = AnonymousUser()
		layouts_admin = admin.site._registry[Layouts]
		form_class = layouts_admin.get_form(request)

		self.assertEqual(form_class.base_fields['manuscript'].to_field_name, 'uuid')

	def test_content_admin_form_uses_uuid_for_formula_field(self):
		request = RequestFactory().get('/admin/')
		request.user = AnonymousUser()
		content_admin = admin.site._registry[Content]
		form_class = content_admin.get_form(request)

		self.assertEqual(form_class.base_fields['formula'].to_field_name, 'uuid')


class ManuscriptUUIDLookupViewTests(TestCase):
	def test_manuscripts_datatable_works_without_project_id_and_exposes_uuid(self):
		manuscript = Manuscripts.objects.create(name='Datatable manuscript', display_as_main=True)

		response = self.client.get(reverse('manuscripts-list'), {'format': 'datatables', 'length': 1})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertGreaterEqual(payload['recordsTotal'], 1)
		self.assertTrue(any(row['uuid'] == str(manuscript.uuid) for row in payload['data']))

	def test_manuscripts_datatable_filters_by_liturgical_genre_uuid(self):
		selected = Manuscripts.objects.create(name='Genre-selected manuscript')
		other = Manuscripts.objects.create(name='Genre-other manuscript')
		genre = LiturgicalGenres.objects.create(title='Sacramentary')
		other_genre = LiturgicalGenres.objects.create(title='Psalter')
		ManuscriptGenres.objects.create(manuscript=selected, genre=genre)
		ManuscriptGenres.objects.create(manuscript=other, genre=other_genre)

		response = self.client.get(
			reverse('manuscripts-list'),
			{'format': 'datatables', 'liturgical_genre': str(genre.uuid), 'length': 10},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['recordsFiltered'], 1)
		self.assertEqual([row['name'] for row in payload['data']], ['Genre-selected manuscript'])

	def test_manuscripts_datatable_filters_by_all_script_name_uuids(self):
		selected = Manuscripts.objects.create(name='Script-selected manuscript')
		partial = Manuscripts.objects.create(name='Script-partial manuscript')
		hand = Hands.objects.create(name='Hand filter')
		script_a = ScriptNames.objects.create(name='Textura')
		script_b = ScriptNames.objects.create(name='Rotunda')

		ManuscriptHands.objects.create(
			manuscript=selected,
			hand=hand,
			script_name=script_a,
			sequence_in_ms=1,
			where_in_ms_from='1r',
		)
		ManuscriptHands.objects.create(
			manuscript=selected,
			hand=hand,
			script_name=script_b,
			sequence_in_ms=2,
			where_in_ms_from='2r',
		)
		ManuscriptHands.objects.create(
			manuscript=partial,
			hand=hand,
			script_name=script_a,
			sequence_in_ms=1,
			where_in_ms_from='3r',
		)

		response = self.client.get(
			reverse('manuscripts-list'),
			{
				'format': 'datatables',
				'script_name_select': f'{script_a.uuid};{script_b.uuid}',
				'length': 10,
			},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['recordsFiltered'], 1)
		self.assertEqual([row['name'] for row in payload['data']], ['Script-selected manuscript'])

	def test_liturgical_genres_autocomplete_returns_uuid(self):
		user = get_user_model().objects.create_user('autocomplete-user', 'auto@example.com', 'secret')
		genre = LiturgicalGenres.objects.create(title='Genre autocomplete')
		self.client.force_login(user)

		response = self.client.get(reverse('liturgical-genres-autocomplete'), {'q': 'Genre'})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		result = next(item for item in payload['results'] if item['text'] == genre.title)
		self.assertEqual(result['uuid'], str(genre.uuid))
		self.assertEqual(result['id'], str(genre.uuid))
		self.assertEqual(result['pk'], str(genre.pk))

	def test_formula_autocomplete_returns_uuid(self):
		user = get_user_model().objects.create_user('formula-autocomplete-user', 'formula-auto@example.com', 'secret')
		formula = Formulas.objects.create(co_no='F-autocomplete', text='Formula autocomplete')
		self.client.force_login(user)

		response = self.client.get(reverse('formula-autocomplete'), {'q': 'Formula'})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		result = next(item for item in payload['results'] if item['text'] == formula.text)
		self.assertEqual(result['uuid'], str(formula.uuid))
		self.assertEqual(str(result['id']), str(formula.uuid))
		self.assertEqual(str(result['pk']), str(formula.pk))

	def test_ritenames_autocomplete_returns_uuid(self):
		user = get_user_model().objects.create_user('ritename-autocomplete-user', 'rite-auto@example.com', 'secret')
		ritename = RiteNames.objects.create(name='Rite autocomplete')
		self.client.force_login(user)

		response = self.client.get(reverse('ritenames-autocomplete'), {'q': 'Rite'})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		result = next(item for item in payload['results'] if item['text'] == ritename.name)
		self.assertEqual(result['uuid'], str(ritename.uuid))
		self.assertEqual(str(result['id']), str(ritename.uuid))
		self.assertEqual(str(result['pk']), str(ritename.pk))

	def test_ms_info_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='UUID manuscript')

		response = self.client.get(reverse('ms_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['manuscript']['uuid'], str(manuscript.uuid))
		self.assertEqual(payload['manuscript']['name'], 'UUID manuscript')

	def test_ms_info_rejects_legacy_manuscript_id_selector(self):
		manuscript = Manuscripts.objects.create(name='Legacy selector manuscript')

		response = self.client.get(reverse('ms_info'), {'manuscript_id': manuscript.id})

		self.assertEqual(response.status_code, 404)

	def test_ms_gallery_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='Gallery manuscript')
		Image.objects.create(manuscript=manuscript, name='Gallery image')

		response = self.client.get(reverse('ms_gallery'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['manuscript_uuid'], str(manuscript.uuid))
		self.assertEqual(len(payload['images']), 1)

	def test_ms_gallery_upload_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='Upload manuscript')
		uploaded = SimpleUploadedFile('gallery.txt', b'abc', content_type='text/plain')

		response = self.client.post(
			reverse('ms_gallery'),
			{'manuscript_uuid': str(manuscript.uuid), 'images': [uploaded]},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Image.objects.filter(manuscript=manuscript).count(), 1)

	def test_content_viewset_filters_by_manuscript_uuid(self):
		selected = Manuscripts.objects.create(name='Selected manuscript', display_as_main=True)
		other = Manuscripts.objects.create(name='Other manuscript', display_as_main=True)
		selected_content = Content.objects.create(manuscript=selected, comments='selected')
		Content.objects.create(manuscript=other, comments='other')

		response = self.client.get(reverse('content-list'), {'manuscript_uuid': str(selected.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['count'], 1)
		self.assertEqual(len(payload['results']), 1)
		self.assertEqual(payload['results'][0]['manuscript_name'], 'Selected manuscript')
		self.assertEqual(payload['results'][0]['uuid'], str(selected_content.uuid))

	def test_hands_viewset_filters_by_manuscript_uuid(self):
		selected = Manuscripts.objects.create(name='Selected hands manuscript')
		other = Manuscripts.objects.create(name='Other hands manuscript')
		hand = Hands.objects.create(name='Hand A')
		script = ScriptNames.objects.create(name='Script A')
		ManuscriptHands.objects.create(
			manuscript=selected,
			hand=hand,
			script_name=script,
			sequence_in_ms=1,
			where_in_ms_from='1r',
		)
		ManuscriptHands.objects.create(
			manuscript=other,
			hand=hand,
			script_name=script,
			sequence_in_ms=2,
			where_in_ms_from='2r',
		)

		response = self.client.get(reverse('hands-list'), {'ms_uuid': str(selected.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['count'], 1)
		self.assertEqual(len(payload['results']), 1)
		self.assertEqual(payload['results'][0]['manuscript'], 'Selected hands manuscript')

	def test_compare_formulas_json_accepts_manuscript_uuid(self):
		left = Manuscripts.objects.create(name='Left compare manuscript')
		right = Manuscripts.objects.create(name='Right compare manuscript')
		formula = Formulas.objects.create(co_no='F-1', text='Formula text')
		Content.objects.create(manuscript=left, formula=formula, sequence_in_ms=1)
		Content.objects.create(manuscript=right, formula=formula, sequence_in_ms=2)

		response = self.client.get(
			reverse('compare_formulas_json'),
			{'left': str(left.uuid), 'right': str(right.uuid)},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 2)
		self.assertEqual({row['Table'] for row in payload}, {'Left compare manuscript', 'Right compare manuscript'})

	def test_ms_tei_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='TEI manuscript')

		response = self.client.get(reverse('ms_tei'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'application/xml')

	def test_ms_tei_rejects_legacy_manuscript_id_selector(self):
		manuscript = Manuscripts.objects.create(name='Legacy TEI manuscript')

		response = self.client.get(reverse('ms_tei'), {'manuscript_id': manuscript.id})

		self.assertEqual(response.status_code, 404)

	def test_manuscript_tei_xml_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='TEI XML manuscript')

		response = self.client.get(reverse('manuscript_tei_xml'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'application/xml')

	def test_content_csv_export_uuid_route_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='CSV manuscript')
		Content.objects.create(manuscript=manuscript, comments='csv row')

		response = self.client.get(reverse('content_csv_export_uuid', kwargs={'manuscript_uuid': manuscript.uuid}))

		self.assertEqual(response.status_code, 200)
		self.assertIn('content_export.csv', response['Content-Disposition'])
		self.assertIn(str(manuscript.id), response.content.decode())

	def test_content_csv_export_legacy_int_route_is_unavailable(self):
		with self.assertRaises(NoReverseMatch):
			reverse('content_csv_export', kwargs={'manuscript_id': 1})

	def test_content_import_accepts_manuscript_uuid_payload(self):
		manuscript = Manuscripts.objects.create(name='Imported manuscript')

		response = self.client.post(
			reverse('content_import'),
			data=json.dumps([
				{
					'manuscript_uuid': str(manuscript.uuid),
					'formula_id': '',
					'formula_text_from_ms': 'Imported text',
					'sequence_in_ms': 1,
					'where_in_ms_from': '1r',
					'where_in_ms_to': '1v',
					'digital_page_number': '',
					'rubric_name_from_ms': '',
					'subrubric_name_from_ms': '',
					'rubric_id': '',
					'rubric_sequence_in_the_MS': '',
					'original_or_added': '',
					'biblical_reference': '',
					'reference_to_other_items': '',
					'edition_index': '',
					'edition_subindex': '',
					'comments': '',
					'function_id': '',
					'subfunction_id': '',
					'liturgical_genre_id': '',
					'music_notation_id': '',
					'quire_id': '',
					'section_id': '',
					'subsection_id': '',
					'contributor_id': '',
					'entry_date': '',
				}
			]),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertJSONEqual(response.content, {'info': 'success'})
		self.assertTrue(Content.objects.filter(manuscript=manuscript, formula_text='Imported text').exists())

	def test_delete_content_uuid_route_accepts_manuscript_uuid(self):
		admin_user = get_user_model().objects.create_superuser('uuid-admin', 'uuid-admin@example.com', 'secret')
		self.client.force_login(admin_user)
		manuscript = Manuscripts.objects.create(name='Delete manuscript')
		Content.objects.create(manuscript=manuscript, comments='delete me')

		response = self.client.delete(reverse('delete_content_uuid', kwargs={'manuscript_uuid': manuscript.uuid}))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['deleted_count'], 1)
		self.assertFalse(Content.objects.filter(manuscript=manuscript).exists())

	def test_delete_content_legacy_int_route_is_unavailable(self):
		with self.assertRaises(NoReverseMatch):
			reverse('delete_content', kwargs={'manuscript_id': 1})

	def test_assign_ms_content_to_tradition_uuid_route_accepts_manuscript_uuid(self):
		admin_user = get_user_model().objects.create_superuser('uuid-admin-2', 'uuid-admin-2@example.com', 'secret')
		self.client.force_login(admin_user)
		manuscript = Manuscripts.objects.create(name='Assign manuscript')
		formula = Formulas.objects.create(co_no='F-assign', text='Assign formula')
		tradition = Traditions.objects.create(name='Assign tradition')
		Content.objects.create(manuscript=manuscript, formula=formula)

		response = self.client.post(
			reverse(
				'assign_ms_content_to_tradition_uuid',
				kwargs={'manuscript_uuid': manuscript.uuid, 'tradition_id': tradition.id},
			),
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['added_count'], 1)
		self.assertTrue(formula.tradition.filter(pk=tradition.pk).exists())

	def test_assign_ms_content_to_tradition_legacy_int_route_is_unavailable(self):
		with self.assertRaises(NoReverseMatch):
			reverse('assign_ms_content_to_tradition', kwargs={'manuscript_id': 1, 'tradition_id': 1})

class AdminUUIDLookupTests(TestCase):
	def test_layout_admin_change_view_accepts_uuid_path(self):
		admin_user = get_user_model().objects.create_superuser('uuid-admin-3', 'uuid-admin-3@example.com', 'secret')
		self.client.force_login(admin_user)
		manuscript = Manuscripts.objects.create(name='Admin UUID manuscript')
		layout = Layouts.objects.create(manuscript=manuscript, where_in_ms_from='1r')

		response = self.client.get(reverse('admin:indexerapp_layouts_change', args=[layout.uuid]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Change layout')

	def test_layout_admin_changelist_link_uses_uuid(self):
		manuscript = Manuscripts.objects.create(name='Admin UUID changelist manuscript')
		layout = Layouts.objects.create(manuscript=manuscript, where_in_ms_from='2r')
		layouts_admin = admin.site._registry[Layouts]

		self.assertEqual(
			layouts_admin.url_for_result(layout),
			reverse('admin:indexerapp_layouts_change', args=[layout.uuid]),
		)
