#!/bin/bash
# Start eCatalogus_main instance — master, port 8000
export DJANGO_SETTINGS_MODULE=ecatalogus.settings_ecatalogus
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8000
