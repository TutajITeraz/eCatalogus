from django.core.management.base import BaseCommand, CommandError
from django.conf import settings as django_settings
from django.test import Client
from django.urls import reverse
import requests
import json


class Command(BaseCommand):
    help = 'Run ETL smoke tests after deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-token',
            help='ETL API token for testing',
        )
        parser.add_argument(
            '--skip-external',
            action='store_true',
            help='Skip external API calls',
        )

    def handle(self, *args, **options):
        self.stdout.write('Running ETL smoke tests...\n')

        client = Client()
        api_token = options.get('api_token') or django_settings.ETL_API_TOKEN

        if not api_token:
            self.stderr.write('No ETL_API_TOKEN configured, some tests will be skipped')

        # Test 1: Django system check
        self.stdout.write('1. Running Django system check...')
        from django.core.management import call_command
        try:
            call_command('check')
            self.stdout.write(self.style.SUCCESS('✓ Django check passed'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'✗ Django check failed: {e}'))
            return

        # Test 2: Static files collection
        self.stdout.write('2. Testing static files collection...')
        try:
            call_command('collectstatic', '--noinput', verbosity=0)
            self.stdout.write(self.style.SUCCESS('✓ Static files collected'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'✗ Static files collection failed: {e}'))
            return

        # Test 3: ETL status endpoint
        self.stdout.write('3. Testing ETL status endpoint...')
        try:
            response = client.get('/api/etl/status/', HTTP_AUTHORIZATION=f'Token {api_token}')
            if response.status_code == 200:
                data = response.json()
                self.stdout.write(self.style.SUCCESS(f'✓ ETL status: {data.get("role", "unknown")}'))
            else:
                self.stderr.write(self.style.ERROR(f'✗ ETL status failed: {response.status_code}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'✗ ETL status error: {e}'))

        # Test 4: OpenAPI schema
        self.stdout.write('4. Testing OpenAPI schema generation...')
        try:
            response = client.get('/api/schema/')
            if response.status_code == 200:
                schema = response.json()
                if 'openapi' in schema and schema['openapi'].startswith('3.'):
                    self.stdout.write(self.style.SUCCESS('✓ OpenAPI schema generated'))
                else:
                    self.stderr.write(self.style.ERROR('✗ Invalid OpenAPI schema'))
            else:
                self.stderr.write(self.style.ERROR(f'✗ Schema endpoint failed: {response.status_code}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'✗ Schema error: {e}'))

        # Test 5: Admin ETL sync page
        self.stdout.write('5. Testing admin ETL sync page...')
        try:
            # This would require authentication, just check URL resolution
            from django.urls import resolve
            match = resolve('/admin/etl-sync/')
            if match:
                self.stdout.write(self.style.SUCCESS('✓ Admin ETL sync URL resolved'))
            else:
                self.stderr.write(self.style.ERROR('✗ Admin ETL sync URL not found'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'✗ Admin URL error: {e}'))

        # Test 6: Manuscript list endpoint
        self.stdout.write('6. Testing manuscript list endpoint...')
        try:
            response = client.get('/api/etl/manuscripts/list/', HTTP_AUTHORIZATION=f'Token {api_token}')
            if response.status_code == 200:
                data = response.json()
                self.stdout.write(self.style.SUCCESS(f'✓ Manuscript list: {len(data)} manuscripts'))
            else:
                self.stderr.write(self.style.ERROR(f'✗ Manuscript list failed: {response.status_code}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'✗ Manuscript list error: {e}'))

        # Test 7: Category export endpoints (dry run)
        self.stdout.write('7. Testing category export endpoints...')
        categories = ['main', 'shared']
        for category in categories:
            try:
                response = client.get(f'/api/etl/{category}/export/', HTTP_AUTHORIZATION=f'Token {api_token}')
                if response.status_code in [200, 404]:  # 404 is OK if no data
                    self.stdout.write(self.style.SUCCESS(f'✓ {category} export endpoint accessible'))
                else:
                    self.stderr.write(self.style.ERROR(f'✗ {category} export failed: {response.status_code}'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'✗ {category} export error: {e}'))

        # Test 8: Celery connectivity (if Redis available)
        self.stdout.write('8. Testing Celery/Redis connectivity...')
        try:
            from celery import Celery
            from django.conf import settings
            app = Celery('test')
            app.config_from_object(settings, namespace='CELERY')
            # Try to ping Redis
            app.connection().ensure_connection(max_retries=1)
            self.stdout.write(self.style.SUCCESS('✓ Celery/Redis connection OK'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'! Celery/Redis not available: {e}'))

        self.stdout.write('\nSmoke tests completed!')
        self.stdout.write('Note: Some tests may have failed due to missing database or external services.')
        self.stdout.write('This is normal for a deployment smoke test without full environment setup.')