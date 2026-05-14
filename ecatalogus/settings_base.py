"""
Django settings base — shared configuration for all eCatalogus instances.

Import this from instance-specific settings files (settings_liturgica.py,
settings_main.py). Do NOT import directly in Django — always use an
instance-specific settings file.

Instance-specific values (NOT here):
  SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS,
  CORS_ALLOWED_ORIGINS, DATABASES, STATICFILES_DIRS
"""

from pathlib import Path
import os
import shlex

BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_env_line(raw_line):
    line = raw_line.strip()
    if not line or line.startswith('#'):
        return None, None

    if line.startswith('export '):
        line = line[7:].strip()

    if '=' not in line:
        return None, None

    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None, None

    if value and value[0] in {'"', "'"}:
        try:
            value = shlex.split(value)[0]
        except ValueError:
            pass

    return key, value


def _load_env_file(env_path, *, override_keys=None):
    if not env_path.exists():
        return

    override_keys = override_keys or set()
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        key, value = _parse_env_line(raw_line)
        if key is None:
            continue
        if key in os.environ and key not in override_keys:
            continue
        os.environ[key] = value


_INITIAL_ENV_KEYS = set(os.environ)
_load_env_file(BASE_DIR / '.env')

_module_name = os.getenv('DJANGO_SETTINGS_MODULE', '')
_instance_env_name = None

if '.' in _module_name:
    _module_short_name = _module_name.rsplit('.', 1)[-1]
else:
    _module_short_name = _module_name

if _module_short_name.startswith('settings_'):
    _instance_slug = _module_short_name[len('settings_'):].strip()
    if _instance_slug:
        _instance_env_name = f'.env.{_instance_slug}'

if _instance_env_name is not None:
    _load_env_file(
        BASE_DIR / _instance_env_name,
        override_keys={key for key in os.environ if key not in _INITIAL_ENV_KEYS},
    )


def csv_env(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


def bool_env(name, default="0"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


SESSION_COOKIE_DOMAIN_DYNAMIC = csv_env(
    'SESSION_COOKIE_DOMAIN_DYNAMIC',
    '.hostline.net.pl,.ispan.pl',
)
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = None
CRSF_COOKIE_SAMESITE = None

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'indexerapp.apps.IndexerappConfig',
    'etlapp.apps.EtlappConfig',
    'data_browser',
    'admin_searchable_dropdown',
    # 'jquery',
    'dal',
    'dal_select2',
    'corsheaders',
    'drf_spectacular',
    'rest_framework_datatables',
    'django_filters',
    'modelclone',
    'iommi',
    #'osm_field'
    #'zotero'
    'captcha',
    'import_export',
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework_datatables.filters.DatatablesFilterBackend',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework_datatables.pagination.DatatablesPageNumberPagination',
    'PAGE_SIZE': 50,
}

DATATABLES = {
    'IGNORE_VALIDATION_ERRORS': True,
}

REST_FRAMEWORK_DATATABLES = {
    'ignore_validation_errors': True,
    'always_serialize': '__all__',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'eCatalogus ETL API',
    'DESCRIPTION': 'OpenAPI schema for ETL synchronization endpoints used by multi-instance dictionary and manuscript replication.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/etl',
    'TAGS': [
        {'name': 'ETL', 'description': 'Machine-to-machine ETL synchronization endpoints.'},
    ],
}

MIDDLEWARE = [
    'iommi.live_edit.Middleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'iommi.sql_trace.Middleware',
    'iommi.profiling.Middleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'iommi.middleware',
]

ROOT_URLCONF = 'ecatalogus.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'indexerapp.context_processors.site_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecatalogus.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static_assets'
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Site identity — override per instance
SITE_NAME = 'eCatalogus'
ETL_ROLE = 'undefined'
ETL_MASTER_URL = None
ETL_SLAVE_URLS = []
ETL_PEER_TOKENS = {}
ETL_API_TOKEN = os.getenv('ETL_API_TOKEN', '')
SITE_SUBTITLE = ''

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
