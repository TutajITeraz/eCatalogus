#!/bin/bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE=ecatalogus.settings_canon-missae

if [[ -f .env.canon-missae ]]; then
  set -a
  source .env.canon-missae
  set +a
fi

source .venv/bin/activate
python manage.py runserver 127.0.0.1:8083
