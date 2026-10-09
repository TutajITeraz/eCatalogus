#!/bin/bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE=ecatalogus.settings_eclla

if [[ -f .env.eclla ]]; then
  set -a
  source .env.eclla
  set +a
fi

source .venv/bin/activate
python manage.py runserver 127.0.0.1:8084
