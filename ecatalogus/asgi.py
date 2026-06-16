"""
ASGI config for ecatalogus project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os

from ecatalogus.env_loader import load_runtime_env
from django.core.asgi import get_asgi_application

settings_module = load_runtime_env()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_asgi_application()
