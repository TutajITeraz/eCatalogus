from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

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
