#!/bin/bash
# Start LiturgicaPoloniae (MPL) instance — slave, port 8080
export DJANGO_SETTINGS_MODULE=ecatalogus.settings_mpl
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8080
