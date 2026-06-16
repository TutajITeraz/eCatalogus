"""
WSGI config for ecatalogus project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os

from ecatalogus.env_loader import load_runtime_env
from django.core.wsgi import get_wsgi_application

settings_module = load_runtime_env()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()
