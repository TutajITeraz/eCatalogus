import json
from unittest.mock import patch

from django.apps import apps
from django.db import models
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse

from etlapp.model_categories import get_sync_model_names
from indexerapp.models import AttributeDebate, Bibliography, Binding, Calendar, Characteristics, Clla, Codicology, Condition, Content, ContentFunctions, Contributors, Day, Decoration, DecorationCharacteristics, DecorationColours, DecorationSubjects, DecorationTechniques, DecorationTypes, FeastRanks, Formulas, Genre, Hands, Image, Layer, Layouts, LiturgicalGenres, MSProjects, ManuscriptBibliography, ManuscriptGenres, ManuscriptHands, ManuscriptMusicNotations, Manuscripts, MassHour, MusicNotationNames, Projects, Provenance, Quires, RiteNames, ScriptNames, SeasonMonth, Sections, Subjects, TextStandarization, TimeReference, Traditions, Week, Colours, EditionContent
from indexerapp.signals import ensure_env_superuser
from indexerapp.views import get_obj_dictionary


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
	def setUp(self):
		self.user = get_user_model().objects.create_superuser(
			username='uuid-admin',
			email='uuid-admin@example.com',
			password='Secret123!pass',
		)
		self.client.force_login(self.user)

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

	def test_projects_admin_changelist_links_use_uuid(self):
		project = Projects.objects.create(name='UUID admin project')

		response = self.client.get(reverse('admin:indexerapp_projects_changelist'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(
			response,
			reverse('admin:indexerapp_projects_change', args=(str(project.uuid),)),
		)

	def test_projects_admin_change_view_accepts_uuid(self):
		project = Projects.objects.create(name='UUID change view project')

		response = self.client.get(reverse('admin:indexerapp_projects_change', args=(str(project.uuid),)))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'UUID change view project')

	def test_codicology_admin_change_view_accepts_uuid_to_field(self):
		manuscript = Manuscripts.objects.create(name='UUID codicology manuscript', display_as_main=True)
		codicology = Codicology.objects.create(manuscript=manuscript)

		response = self.client.get(
			reverse('admin:indexerapp_codicology_change', args=(str(codicology.uuid),)),
			{'_to_field': 'uuid', '_popup': '1'},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Change codicology')
		self.assertContains(response, 'name="_to_field" value="uuid"', html=False)

	def test_manuscript_watermarks_add_view_accepts_uuid_to_field(self):
		manuscript = Manuscripts.objects.create(name='UUID watermark manuscript', display_as_main=True)

		response = self.client.get(
			reverse('admin:indexerapp_manuscriptwatermarks_add'),
			{'_to_field': 'uuid', '_popup': '1', 'manuscript': str(manuscript.uuid)},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Add manuscript watermarks')
		self.assertContains(response, 'name="_to_field" value="uuid"', html=False)


class ManuscriptUUIDLookupViewTests(TestCase):
	def test_manuscripts_datatable_works_without_project_id_and_exposes_uuid(self):
		manuscript = Manuscripts.objects.create(name='Datatable manuscript', display_as_main=True)

		response = self.client.get(reverse('manuscripts-list'), {'format': 'datatables', 'length': 1})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertGreaterEqual(payload['recordsTotal'], 1)
		row = next(item for item in payload['data'] if item['uuid'] == str(manuscript.uuid))
		self.assertNotIn('id', row)

	def test_manuscripts_datatable_exposes_source_project_metadata(self):
		manuscript = Manuscripts.objects.create(name='Project metadata manuscript', display_as_main=True)
		project = Projects.objects.create(
			name='eCatalogus source',
			icon='https://example.com/logo.png',
			project_url='https://example.com/project',
		)
		MSProjects.objects.create(manuscript=manuscript, project=project)

		response = self.client.get(reverse('manuscripts-list'), {'format': 'datatables', 'length': 10})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		row = next(item for item in payload['data'] if item['uuid'] == str(manuscript.uuid))
		self.assertEqual(row['source_project_name'], 'eCatalogus source')
		self.assertEqual(row['source_project_icon'], 'https://example.com/logo.png')
		self.assertEqual(row['source_project_url'], 'https://example.com/project')
		self.assertEqual(row['source_project_uuid'], str(project.uuid))

	def test_manuscripts_datatable_filters_by_source_project_uuid(self):
		selected = Manuscripts.objects.create(name='Selected source project manuscript', display_as_main=True)
		other = Manuscripts.objects.create(name='Other source project manuscript', display_as_main=True)
		selected_project = Projects.objects.create(name='Selected project')
		other_project = Projects.objects.create(name='Other project')
		MSProjects.objects.create(manuscript=selected, project=selected_project)
		MSProjects.objects.create(manuscript=other, project=other_project)

		response = self.client.get(
			reverse('manuscripts-list'),
			{'format': 'datatables', 'source_project': str(selected_project.uuid), 'length': 10},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['recordsFiltered'], 1)
		self.assertEqual([row['name'] for row in payload['data']], ['Selected source project manuscript'])

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

	def test_projects_autocomplete_returns_uuid(self):
		user = get_user_model().objects.create_user('project-autocomplete-user', 'project-auto@example.com', 'secret')
		project = Projects.objects.create(name='Project autocomplete')
		manuscript = Manuscripts.objects.create(name='Autocomplete manuscript', display_as_main=True)
		MSProjects.objects.create(manuscript=manuscript, project=project)
		self.client.force_login(user)

		response = self.client.get(reverse('projects-autocomplete'), {'q': 'Project'})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		result = next(item for item in payload['results'] if item['text'] == project.name)
		self.assertEqual(result['uuid'], str(project.uuid))
		self.assertEqual(str(result['id']), str(project.uuid))
		self.assertEqual(str(result['pk']), str(project.pk))

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

	def test_formulas_index_used_in_links_are_uuid_first(self):
		manuscript = Manuscripts.objects.create(name='Formula index manuscript')
		formula = Formulas.objects.create(co_no='F-index', text='Formula index text')
		Content.objects.create(manuscript=manuscript, formula=formula, sequence_in_ms=1)

		response = self.client.get(reverse('formulas_index-list'))

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		row = next(item for item in payload['results'] if item['id'] == formula.id)
		self.assertEqual(row['used_in'][0]['uuid'], str(manuscript.uuid))
		self.assertNotIn('id', row['used_in'][0])

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

	def test_rites_index_used_in_links_are_uuid_first(self):
		manuscript = Manuscripts.objects.create(name='Rites index manuscript')
		ritename = RiteNames.objects.create(name='Rite index name')
		Content.objects.create(manuscript=manuscript, rubric=ritename, sequence_in_ms=1)

		response = self.client.get(reverse('rites_index-list'))

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		row = next(item for item in payload['results'] if item['id'] == ritename.id)
		self.assertEqual(row['used_in'][0]['uuid'], str(manuscript.uuid))
		self.assertNotIn('id', row['used_in'][0])

	def test_subjects_index_used_in_links_are_uuid_first(self):
		manuscript = Manuscripts.objects.create(name='Subjects index manuscript')
		subject = Subjects.objects.create(name='Subject index name')
		decoration_type = DecorationTypes.objects.create(name='Initial')
		decoration = Decoration.objects.create(
			manuscript=manuscript,
			decoration_type=decoration_type,
			where_in_ms_from='1r',
		)
		DecorationSubjects.objects.create(decoration=decoration, subject=subject)

		response = self.client.get(reverse('subjects_index-list'))

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		row = next(item for item in payload['results'] if item['id'] == subject.id)
		self.assertEqual(row['used_in'][0]['uuid'], str(manuscript.uuid))
		self.assertNotIn('id', row['used_in'][0])

	def test_ms_info_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='UUID manuscript')

		response = self.client.get(reverse('ms_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['manuscript']['uuid'], str(manuscript.uuid))
		self.assertEqual(payload['manuscript']['name'], 'UUID manuscript')

	def test_ms_info_reads_debate_bound_by_object_uuid(self):
		manuscript = Manuscripts.objects.create(name='UUID debate manuscript')
		bibliography = Bibliography.objects.create(title='UUID debate bibliography')
		content_type = ContentType.objects.get_for_model(Manuscripts)
		AttributeDebate.objects.create(
			content_type=content_type,
			object_uuid=manuscript.uuid,
			bibliography=bibliography,
			field_name='name',
			text='UUID debate text',
		)

		response = self.client.get(reverse('ms_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['debate'][0]['text'], 'UUID debate text')
		self.assertEqual(payload['debate'][0]['field_name'], 'name')

	def test_attribute_debate_content_object_resolves_by_object_uuid(self):
		manuscript = Manuscripts.objects.create(name='UUID-bound debate manuscript')
		bibliography = Bibliography.objects.create(title='UUID-bound debate bibliography')
		content_type = ContentType.objects.get_for_model(Manuscripts)

		debate = AttributeDebate.objects.create(
			content_type=content_type,
			object_uuid=manuscript.uuid,
			bibliography=bibliography,
			field_name='name',
			text='UUID debate text',
		)

		self.assertEqual(debate.content_object, manuscript)

	def test_get_obj_dictionary_keeps_uuid_fk_values_raw(self):
		manuscript = Manuscripts.objects.create(name='Dictionary manuscript')
		condition = Condition.objects.create(manuscript=manuscript)

		payload = get_obj_dictionary(condition, skip_fields=[])

		self.assertEqual(payload['manuscript_uuid'], str(manuscript.uuid))

	def test_ms_info_exposes_source_project_metadata(self):
		manuscript = Manuscripts.objects.create(name='UUID manuscript with source project')
		project = Projects.objects.create(
			name='Main info project',
			icon='https://example.com/main-info-project.svg',
			project_url='https://example.com/main-info-project',
		)
		MSProjects.objects.create(manuscript=manuscript, project=project)

		response = self.client.get(reverse('ms_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['manuscript']['source_project_name'], 'Main info project')
		self.assertEqual(payload['manuscript']['source_project_icon'], 'https://example.com/main-info-project.svg')
		self.assertEqual(payload['manuscript']['source_project_url'], 'https://example.com/main-info-project')

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
		self.assertNotIn('manuscript_id', payload)
		self.assertEqual(len(payload['images']), 1)
		self.assertEqual(payload['images'][0]['uuid'], str(manuscript.images.first().uuid))
		self.assertNotIn('id', payload['images'][0])

	def test_ms_gallery_upload_accepts_manuscript_uuid(self):
		manuscript = Manuscripts.objects.create(name='Upload manuscript')
		uploaded = SimpleUploadedFile('gallery.txt', b'abc', content_type='text/plain')

		response = self.client.post(
			reverse('ms_gallery'),
			{'manuscript_uuid': str(manuscript.uuid), 'images': [uploaded]},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Image.objects.filter(manuscript=manuscript).count(), 1)
		self.assertIn('uuid', response.json()['created'][0])

	def test_ms_gallery_delete_accepts_image_uuid(self):
		manuscript = Manuscripts.objects.create(name='Delete gallery manuscript')
		image = Image.objects.create(manuscript=manuscript, name='Delete image')

		response = self.client.delete(
			reverse('ms_gallery'),
			data=json.dumps({'manuscript_uuid': str(manuscript.uuid), 'image_uuid': str(image.uuid)}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['image_uuid'], str(image.uuid))
		self.assertFalse(Image.objects.filter(pk=image.pk).exists())

	def test_layouts_info_uses_uuid_without_legacy_id(self):
		manuscript = Manuscripts.objects.create(name='Layouts manuscript')
		layout = Layouts.objects.create(manuscript=manuscript, name='Layout A')

		response = self.client.get(reverse('layouts_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['data'][0]['uuid'], str(layout.uuid))
		self.assertNotIn('id', payload['data'][0])

	def test_condition_info_uses_uuid_without_legacy_id(self):
		manuscript = Manuscripts.objects.create(name='Condition manuscript')
		condition = Condition.objects.create(manuscript=manuscript)

		response = self.client.get(reverse('condition_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['data'][0]['uuid'], str(condition.uuid))
		self.assertNotIn('id', payload['data'][0])

	def test_decoration_info_keeps_uuid_payloads_after_shadow_fk_conversion(self):
		manuscript = Manuscripts.objects.create(name='Decoration manuscript')
		formula = Formulas.objects.create(co_no='Decor-formula', text='Decoration content formula')
		content = Content.objects.create(manuscript=manuscript, formula=formula, sequence_in_ms=1)
		feast_rank = FeastRanks.objects.create(name='Major feast')
		calendar = Calendar.objects.create(
			manuscript=manuscript,
			content=content,
			feast_rank=feast_rank,
			latin_name='Kal. Ian.',
			feast_name='Circumcision',
			littera_dominicalis='A',
		)
		decoration_type = DecorationTypes.objects.create(name='Initial')
		decoration = Decoration.objects.create(
			manuscript=manuscript,
			content=content,
			calendar=calendar,
			decoration_type=decoration_type,
			where_in_ms_from='1r',
		)

		response = self.client.get(reverse('decoration_info'), {'manuscript_uuid': str(manuscript.uuid)})

		self.assertEqual(response.status_code, 200)
		payload = response.json()['data'][0]
		self.assertEqual(payload['uuid'], str(decoration.uuid))
		self.assertEqual(payload['manuscript_uuid'], str(manuscript.uuid))
		self.assertEqual(payload['content_uuid'], str(content.uuid))
		self.assertEqual(payload['calendar_uuid'], str(calendar.uuid))
		self.assertEqual(payload['decoration_type_uuid'], str(decoration_type.uuid))
		self.assertNotIn('id', payload)

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
		self.assertNotIn('id', payload['results'][0])

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
		self.assertNotIn('id', payload['results'][0])

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
		self.assertIn('manuscript_uuid', response.content.decode())
		self.assertIn(str(manuscript.uuid), response.content.decode())

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

	def test_content_import_rejects_legacy_manuscript_id_payload(self):
		manuscript = Manuscripts.objects.create(name='Legacy imported manuscript')

		response = self.client.post(
			reverse('content_import'),
			data=json.dumps([
				{
					'manuscript_id': manuscript.id,
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
		self.assertIn('could not resolve manuscript selector', response.json()['info'])

	def test_clla_import_accepts_manuscript_uuid_payload(self):
		manuscript = Manuscripts.objects.create(name='CLLA manuscript')

		response = self.client.post(
			reverse('clla_import'),
			data=json.dumps([
				{
					'manuscript_uuid': str(manuscript.uuid),
					'clla_no': 'CLLA 1',
					'liturgical_genre': 'genre',
					'dating': '',
					'dating_comment': '',
					'provenance': '',
					'provenance_comment': '',
					'comment': 'note',
				}
			]),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertJSONEqual(response.content, {'info': 'success'})
		self.assertTrue(Clla.objects.filter(manuscript=manuscript, clla_no='CLLA 1').exists())

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

	def test_image_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Image UUID FK manuscript')

		image = Image.objects.create(manuscript=manuscript, name='UUID image')

		self.assertEqual(image.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(image.manuscript_uuid, manuscript)

	def test_msprojects_shadow_uuids_are_real_uuid_fks(self):
		manuscript = Manuscripts.objects.create(name='MSProjects UUID FK manuscript')
		project = Projects.objects.create(name='UUID project')

		relation = MSProjects.objects.create(manuscript=manuscript, project=project)

		self.assertEqual(relation.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(relation.project_uuid_id, project.uuid)
		self.assertEqual(relation.manuscript_uuid, manuscript)
		self.assertEqual(relation.project_uuid, project)

	def test_layout_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Layouts UUID FK manuscript')

		layout = Layouts.objects.create(manuscript=manuscript, where_in_ms_from='3r')

		self.assertEqual(layout.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(layout.manuscript_uuid, manuscript)

	def test_codicology_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Codicology UUID FK manuscript')

		codicology = Codicology.objects.create(manuscript=manuscript)

		self.assertEqual(codicology.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(codicology.manuscript_uuid, manuscript)

	def test_condition_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Condition UUID FK manuscript')

		condition = Condition.objects.create(manuscript=manuscript)

		self.assertEqual(condition.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(condition.manuscript_uuid, manuscript)

	def test_manuscripthands_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Hands UUID FK manuscript')
		hand = Hands.objects.create(name='UUID FK hand')
		script = ScriptNames.objects.create(name='UUID FK script')

		relation = ManuscriptHands.objects.create(
			manuscript=manuscript,
			hand=hand,
			script_name=script,
			sequence_in_ms=1,
			where_in_ms_from='1r',
		)

		self.assertEqual(relation.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(relation.manuscript_uuid, manuscript)

	def test_provenance_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Provenance UUID FK manuscript')

		provenance = Provenance.objects.create(manuscript=manuscript, timeline_sequence=1)

		self.assertEqual(provenance.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(provenance.manuscript_uuid, manuscript)

	def test_binding_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Binding UUID FK manuscript')

		binding = Binding.objects.create(manuscript=manuscript)

		self.assertEqual(binding.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(binding.manuscript_uuid, manuscript)

	def test_manuscriptbibliography_shadow_uuid_is_real_uuid_fk(self):
		manuscript = Manuscripts.objects.create(name='Bibliography UUID FK manuscript')
		bibliography = Bibliography.objects.create(title='UUID FK bibliography')

		relation = ManuscriptBibliography.objects.create(manuscript=manuscript, bibliography=bibliography)

		self.assertEqual(relation.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(relation.manuscript_uuid, manuscript)

	def test_calendar_shadow_uuids_are_real_uuid_fks(self):
		manuscript = Manuscripts.objects.create(name='Calendar UUID FK manuscript')
		formula = Formulas.objects.create(co_no='CAL-UUID', text='Calendar UUID formula')
		content = Content.objects.create(manuscript=manuscript, formula=formula, sequence_in_ms=1)
		rubric = RiteNames.objects.create(name='Calendar UUID rubric')
		feast_rank = FeastRanks.objects.create(name='Calendar UUID feast rank')
		time_reference = TimeReference.objects.create(
			time_description='Calendar UUID time',
			century_from=12,
			century_to=12,
			year_from=1100,
			year_to=1199,
		)
		contributor = Contributors.objects.create(initials='CAL', first_name='Cal', last_name='Contributor')

		calendar = Calendar.objects.create(
			manuscript=manuscript,
			rubric_name_standarized=rubric,
			content=content,
			feast_rank=feast_rank,
			date_of_the_addition=time_reference,
			data_contributor=contributor,
			latin_name='Kal. Ian.',
			feast_name='Circumcision',
			littera_dominicalis='A',
		)

		self.assertEqual(calendar.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(calendar.rubric_name_standarized_uuid_id, rubric.uuid)
		self.assertEqual(calendar.content_uuid_id, content.uuid)
		self.assertEqual(calendar.feast_rank_uuid_id, feast_rank.uuid)
		self.assertEqual(calendar.date_of_the_addition_uuid_id, time_reference.uuid)
		self.assertEqual(calendar.data_contributor_uuid_id, contributor.uuid)
		self.assertEqual(calendar.manuscript_uuid, manuscript)
		self.assertEqual(calendar.content_uuid, content)

	def test_content_shadow_uuids_are_real_uuid_fks(self):
		manuscript = Manuscripts.objects.create(name='Content UUID FK manuscript')
		formula = Formulas.objects.create(co_no='CNT-UUID', text='Content UUID formula')
		rubric = RiteNames.objects.create(name='Content UUID rubric')
		liturgical_genre = LiturgicalGenres.objects.create(title='Content UUID genre')
		quire = Quires.objects.create(
			manuscript=manuscript,
			sequence_of_the_quire=1,
			type_of_the_quire='binion',
			where_in_ms_from='1r',
		)
		section = Sections.objects.create(name='Content UUID section')
		subsection = Sections.objects.create(name='Content UUID subsection')
		music_notation_name = MusicNotationNames.objects.create(name='Content UUID notation')
		music_notation = ManuscriptMusicNotations.objects.create(
			manuscript=manuscript,
			music_notation_name=music_notation_name,
			sequence_in_ms=1,
			where_in_ms_from='1r',
		)
		function = ContentFunctions.objects.create(name='Content UUID function')
		subfunction = ContentFunctions.objects.create(name='Content UUID subfunction')
		contributor = Contributors.objects.create(initials='CNT', first_name='Con', last_name='Tributor')
		bibliography = Bibliography.objects.create(title='Content UUID bibliography')
		edition_index = EditionContent.objects.create(bibliography=bibliography)
		text_standarization = TextStandarization.objects.create(standard_incipit='Content UUID text')
		layer = Layer.objects.create(short_name='L1', name='Layer One')
		mass_hour = MassHour.objects.create(short_name='MH1', name='Mass Hour One')
		genre = Genre.objects.create(short_name='G1', name='Genre One')
		season_month = SeasonMonth.objects.create(short_name='SM1', name='Season Month One', kind='S')
		week = Week.objects.create(short_name='W1', name='Week One')
		day = Day.objects.create(short_name='D1', name='Day One', part='T')

		content = Content.objects.create(
			manuscript=manuscript,
			formula=formula,
			rubric=rubric,
			liturgical_genre=liturgical_genre,
			quire=quire,
			section=section,
			subsection=subsection,
			music_notation=music_notation,
			function=function,
			subfunction=subfunction,
			data_contributor=contributor,
			edition_index=edition_index,
			text_standarization=text_standarization,
			layer=layer,
			mass_hour=mass_hour,
			genre=genre,
			season_month=season_month,
			week=week,
			day=day,
			sequence_in_ms=1,
		)

		self.assertEqual(content.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(content.formula_uuid_id, formula.uuid)
		self.assertEqual(content.rubric_uuid_id, rubric.uuid)
		self.assertEqual(content.liturgical_genre_uuid_id, liturgical_genre.uuid)
		self.assertEqual(content.quire_uuid_id, quire.uuid)
		self.assertEqual(content.section_uuid_id, section.uuid)
		self.assertEqual(content.subsection_uuid_id, subsection.uuid)
		self.assertEqual(content.music_notation_uuid_id, music_notation.uuid)
		self.assertEqual(content.function_uuid_id, function.uuid)
		self.assertEqual(content.subfunction_uuid_id, subfunction.uuid)
		self.assertEqual(content.data_contributor_uuid_id, contributor.uuid)
		self.assertEqual(content.edition_index_uuid_id, edition_index.uuid)
		self.assertEqual(content.text_standarization_uuid_id, text_standarization.uuid)
		self.assertEqual(content.layer_uuid_id, layer.uuid)
		self.assertEqual(content.mass_hour_uuid_id, mass_hour.uuid)
		self.assertEqual(content.genre_uuid_id, genre.uuid)
		self.assertEqual(content.season_month_uuid_id, season_month.uuid)
		self.assertEqual(content.week_uuid_id, week.uuid)
		self.assertEqual(content.day_uuid_id, day.uuid)

	def test_decoration_shadow_uuids_are_real_uuid_fks(self):
		manuscript = Manuscripts.objects.create(name='Decoration UUID FK manuscript')
		formula = Formulas.objects.create(co_no='DEC-UUID', text='Decoration UUID formula')
		content = Content.objects.create(manuscript=manuscript, formula=formula, sequence_in_ms=1)
		feast_rank = FeastRanks.objects.create(name='Decoration UUID feast rank')
		calendar = Calendar.objects.create(
			manuscript=manuscript,
			content=content,
			feast_rank=feast_rank,
			latin_name='Kal. Feb.',
			feast_name='Purification',
			littera_dominicalis='B',
		)
		date_of_addition = TimeReference.objects.create(
			time_description='Decoration UUID time',
			century_from=13,
			century_to=13,
			year_from=1200,
			year_to=1299,
		)
		decoration_type = DecorationTypes.objects.create(name='Decoration UUID type')
		decoration_subtype = DecorationTypes.objects.create(name='Decoration UUID subtype')
		technique = DecorationTechniques.objects.create(name='Decoration UUID technique')
		rubric = RiteNames.objects.create(name='Decoration UUID rubric')
		contributor = Contributors.objects.create(initials='DEC', first_name='Dec', last_name='Contributor')

		decoration = Decoration.objects.create(
			manuscript=manuscript,
			date_of_the_addition=date_of_addition,
			content=content,
			calendar=calendar,
			decoration_type=decoration_type,
			decoration_subtype=decoration_subtype,
			technique=technique,
			rubric_name_standarized=rubric,
			data_contributor=contributor,
			where_in_ms_from='1r',
		)

		self.assertEqual(decoration.manuscript_uuid_id, manuscript.uuid)
		self.assertEqual(decoration.date_of_the_addition_uuid_id, date_of_addition.uuid)
		self.assertEqual(decoration.content_uuid_id, content.uuid)
		self.assertEqual(decoration.calendar_uuid_id, calendar.uuid)
		self.assertEqual(decoration.decoration_type_uuid_id, decoration_type.uuid)
		self.assertEqual(decoration.decoration_subtype_uuid_id, decoration_subtype.uuid)
		self.assertEqual(decoration.technique_uuid_id, technique.uuid)
		self.assertEqual(decoration.rubric_name_standarized_uuid_id, rubric.uuid)
		self.assertEqual(decoration.data_contributor_uuid_id, contributor.uuid)

	def test_decoration_detail_shadow_uuids_are_real_uuid_fks(self):
		manuscript = Manuscripts.objects.create(name='Decoration detail UUID FK manuscript')
		formula = Formulas.objects.create(co_no='DET-UUID', text='Decoration detail UUID formula')
		content = Content.objects.create(manuscript=manuscript, formula=formula, sequence_in_ms=1)
		feast_rank = FeastRanks.objects.create(name='Decoration detail feast rank')
		calendar = Calendar.objects.create(
			manuscript=manuscript,
			content=content,
			feast_rank=feast_rank,
			latin_name='Kal. Mar.',
			feast_name='Annunciation',
			littera_dominicalis='C',
		)
		decoration_type = DecorationTypes.objects.create(name='Decoration detail type')
		decoration = Decoration.objects.create(
			manuscript=manuscript,
			content=content,
			calendar=calendar,
			decoration_type=decoration_type,
			where_in_ms_from='2r',
		)
		subject = Subjects.objects.create(name='Decoration detail subject')
		colour = Colours.objects.create(name='Decoration detail colour')
		characteristics = Characteristics.objects.create(name='Decoration detail characteristics')

		decoration_subject = DecorationSubjects.objects.create(decoration=decoration, subject=subject)
		decoration_colour = DecorationColours.objects.create(decoration=decoration, colour=colour)
		decoration_characteristics = DecorationCharacteristics.objects.create(
			decoration=decoration,
			characteristics=characteristics,
		)

		self.assertEqual(decoration_subject.decoration_uuid_id, decoration.uuid)
		self.assertEqual(decoration_subject.subject_uuid_id, subject.uuid)
		self.assertEqual(decoration_colour.decoration_uuid_id, decoration.uuid)
		self.assertEqual(decoration_colour.colour_uuid_id, colour.uuid)
		self.assertEqual(decoration_characteristics.decoration_uuid_id, decoration.uuid)
		self.assertEqual(decoration_characteristics.characteristics_uuid_id, characteristics.uuid)

	def test_all_sync_shadow_uuid_fields_are_real_uuid_foreign_keys(self):
		for model_name in get_sync_model_names():
			model = apps.get_model('indexerapp', model_name)
			for field in model._meta.concrete_fields:
				if not isinstance(field, models.ForeignKey):
					continue

				shadow_name = f'{field.name}_uuid'
				try:
					shadow_field = model._meta.get_field(shadow_name)
				except Exception:
					continue

				self.assertIsInstance(shadow_field, models.ForeignKey, f'{model_name}.{shadow_name}')
				self.assertEqual(shadow_field.target_field.name, 'uuid', f'{model_name}.{shadow_name}')

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
