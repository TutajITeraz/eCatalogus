"""Instance settings for Liturgica Poloniae (MPL). Safe to commit; secrets live in .env."""

from .settings_base import *


DEFAULT_ALLOWED_HOSTS = ','.join([
    'monumenta-poloniae-liturgica.ispan.pl',
    'indexer.rebold.hostline.net.pl',
    'server.hostline.pl',
    'eclla.hostline.net.pl',
    '127.0.0.1',
    'localhost',
])

DEFAULT_CSRF_TRUSTED_ORIGINS = ','.join([
    'https://monumenta-poloniae-liturgica.ispan.pl',
    'http://monumenta-poloniae-liturgica.ispan.pl',
    'https://indexer.rebold.hostline.net.pl',
    'http://indexer.rebold.hostline.net.pl',
    'https://eclla.hostline.net.pl',
    'http://eclla.hostline.net.pl',
    'https://lp.hostline.net.pl',
    'http://lp.hostline.net.pl',
    'https://liturgicapoloniae.hostline.net.pl',
    'http://liturgicapoloniae.hostline.net.pl',
    'https://127.0.0.1',
    'http://127.0.0.1',
])

DEFAULT_CORS_ALLOWED_ORIGINS = ','.join([
    'http://localhost:3000',
    'http://indexer.rebold.hostline.net.pl',
    'https://indexer.rebold.hostline.net.pl',
    'https://polona.pl',
    'https://collections.library.yale.edu',
    'http://polona.pl',
    'http://collections.library.yale.edu',
    'http://eclla.hostline.net.pl',
    'https://eclla.hostline.net.pl',
    'http://lp.hostline.net.pl',
    'https://lp.hostline.net.pl',
    'http://liturgicapoloniae.hostline.net.pl',
    'https://liturgicapoloniae.hostline.net.pl',
    'http://monumenta-poloniae-liturgica.ispan.pl',
    'https://monumenta-poloniae-liturgica.ispan.pl',
])

SECRET_KEY = os.getenv('MPL_SECRET_KEY', os.getenv('SECRET_KEY', 'mpl-secret-key-change-me'))
DEBUG = bool_env('MPL_DEBUG', os.getenv('DEBUG', '0'))

ALLOWED_HOSTS = csv_env(
    'MPL_ALLOWED_HOSTS',
    os.getenv('ALLOWED_HOSTS', DEFAULT_ALLOWED_HOSTS),
)

CSRF_TRUSTED_ORIGINS = csv_env(
    'MPL_CSRF_TRUSTED_ORIGINS',
    os.getenv('CSRF_TRUSTED_ORIGINS', DEFAULT_CSRF_TRUSTED_ORIGINS),
)

CORS_ALLOWED_ORIGINS = csv_env(
    'MPL_CORS_ALLOWED_ORIGINS',
    os.getenv('CORS_ALLOWED_ORIGINS', DEFAULT_CORS_ALLOWED_ORIGINS),
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'CONN_MAX_AGE': 0,
        'NAME': os.getenv('MPL_DATABASE_NAME', os.getenv('DATABASE_NAME', 'ispan_mpl')),
        'USER': os.getenv('MPL_DATABASE_USER', os.getenv('DATABASE_USER', 'ispan_mpl')),
        'PASSWORD': os.getenv('MPL_DATABASE_PASSWORD', os.getenv('DATABASE_PASSWORD', '')),
        'HOST': os.getenv('MPL_DATABASE_HOST', os.getenv('DATABASE_HOST', '127.0.0.1')),
        'PORT': os.getenv('MPL_DATABASE_PORT', os.getenv('DATABASE_PORT', '3306')),
    }
}

# Overlay: MPL-specific static files take precedence over shared base
STATICFILES_DIRS = [
    BASE_DIR / "static_mpl",        # MPL overlay (logo, branding)
    BASE_DIR / "indexerapp/static", # shared base
]

MEDIA_ROOT = os.getenv(
    'MPL_MEDIA_ROOT',
    os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media_instances' / 'mpl')),
)

SITE_NAME = 'Liturgica Poloniae'
SESSION_COOKIE_NAME = os.getenv('MPL_SESSION_COOKIE_NAME', os.getenv('SESSION_COOKIE_NAME', 'mpl_sessionid'))
CSRF_COOKIE_NAME = os.getenv('MPL_CSRF_COOKIE_NAME', os.getenv('CSRF_COOKIE_NAME', 'mpl_csrftoken'))

ETL_ROLE = 'slave'
ETL_MASTER_URL = os.getenv('MPL_ETL_MASTER_URL', os.getenv('ETL_MASTER_URL', 'https://ecatalogus.ispan.pl'))
ETL_API_TOKEN = os.getenv('MPL_ETL_API_TOKEN', os.getenv('ETL_API_TOKEN', 'mpl-token-change-me'))
ETL_PEER_TOKENS = {
    ETL_MASTER_URL: os.getenv('MPL_ETL_MASTER_API_TOKEN', os.getenv('ETL_MASTER_API_TOKEN', 'ecatalogus-main-token-change-me')),
}
