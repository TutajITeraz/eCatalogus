"""Instance settings for eCatalogus. Safe to commit; secrets live in .env."""

from .settings_base import *


DEFAULT_ALLOWED_HOSTS = ','.join([
    'ecatalogus.ispan.pl',
    '127.0.0.1',
    'localhost',
])

DEFAULT_CSRF_TRUSTED_ORIGINS = ','.join([
    'https://ecatalogus.ispan.pl',
    'http://ecatalogus.ispan.pl',
    'https://127.0.0.1',
    'http://127.0.0.1',
])

DEFAULT_CORS_ALLOWED_ORIGINS = ','.join([
    'http://localhost:3000',
    'http://localhost:8000',
    'https://ecatalogus.ispan.pl',
    'http://ecatalogus.ispan.pl',
])

SECRET_KEY = os.getenv('ECATALOGUS_SECRET_KEY', os.getenv('SECRET_KEY', 'ecatalogus-main-secret-key-change-me'))
DEBUG = bool_env('ECATALOGUS_DEBUG', os.getenv('DEBUG', '0'))

ALLOWED_HOSTS = csv_env(
    'ECATALOGUS_ALLOWED_HOSTS',
    os.getenv('ALLOWED_HOSTS', DEFAULT_ALLOWED_HOSTS),
)

CSRF_TRUSTED_ORIGINS = csv_env(
    'ECATALOGUS_CSRF_TRUSTED_ORIGINS',
    os.getenv('CSRF_TRUSTED_ORIGINS', DEFAULT_CSRF_TRUSTED_ORIGINS),
)

CORS_ALLOWED_ORIGINS = csv_env(
    'ECATALOGUS_CORS_ALLOWED_ORIGINS',
    os.getenv('CORS_ALLOWED_ORIGINS', DEFAULT_CORS_ALLOWED_ORIGINS),
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'CONN_MAX_AGE': 0,
        'NAME': os.getenv('ECATALOGUS_DATABASE_NAME', os.getenv('DATABASE_NAME', 'ecatalogus')),
        'USER': os.getenv('ECATALOGUS_DATABASE_USER', os.getenv('DATABASE_USER', 'ecatalogus_user')),
        'PASSWORD': os.getenv('ECATALOGUS_DATABASE_PASSWORD', os.getenv('DATABASE_PASSWORD', '')),
        'HOST': os.getenv('ECATALOGUS_DATABASE_HOST', os.getenv('DATABASE_HOST', '127.0.0.1')),
        'PORT': os.getenv('ECATALOGUS_DATABASE_PORT', os.getenv('DATABASE_PORT', '3306')),
    }
}

# Overlay: eCatalogus-specific static files take precedence over shared base
STATICFILES_DIRS = [
    BASE_DIR / "static_ecatalogus", # eCatalogus overlay (logo, branding)
    BASE_DIR / "indexerapp/static", # shared base
]

MEDIA_ROOT = os.getenv(
    'ECATALOGUS_MEDIA_ROOT',
    os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media_instances' / 'ecatalogus')),
)

SITE_NAME = 'eCatalogus'
SESSION_COOKIE_NAME = os.getenv('ECATALOGUS_SESSION_COOKIE_NAME', os.getenv('SESSION_COOKIE_NAME', 'ecatalogus_sessionid'))
CSRF_COOKIE_NAME = os.getenv('ECATALOGUS_CSRF_COOKIE_NAME', os.getenv('CSRF_COOKIE_NAME', 'ecatalogus_csrftoken'))

ETL_ROLE = 'master'
ETL_MASTER_URL = None
ETL_SLAVE_URLS = csv_env(
    'ECATALOGUS_ETL_SLAVE_URLS',
    os.getenv('ETL_SLAVE_URLS', 'https://monumenta-poloniae-liturgica.ispan.pl'),
)
ETL_API_TOKEN = os.getenv('ECATALOGUS_ETL_API_TOKEN', os.getenv('ETL_API_TOKEN', 'ecatalogus-main-token-change-me'))
ETL_PEER_TOKENS = {
    slave_url: os.getenv('ECATALOGUS_ETL_MPL_API_TOKEN', os.getenv('ETL_MPL_API_TOKEN', 'mpl-token-change-me'))
    for slave_url in ETL_SLAVE_URLS
}
