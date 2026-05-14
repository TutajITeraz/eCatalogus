#!/bin/bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE=ecatalogus.settings_limbo

if [[ -f .env.limbo ]]; then
  set -a
  source .env.limbo
  set +a
fi

source .venv/bin/activate
python manage.py runserver 127.0.0.1:8081
