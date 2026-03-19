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

BASE_DIR = Path(__file__).resolve().parent.parent


SESSION_COOKIE_DOMAIN_DYNAMIC = ['.hostline.net.pl']
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
    'data_browser',
    'admin_searchable_dropdown',
    # 'jquery',
    'dal',
    'dal_select2',
    'corsheaders',
    'rest_framework_datatables',
    'django_filters',
    'modelclone',
    'iommi',
    #'osm_field'
    #'zotero'
    'captcha'
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
    ),
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
SITE_SUBTITLE = ''
