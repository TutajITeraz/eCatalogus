#!/bin/bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE=ecatalogus.settings_corpus-liturgicum

if [[ -f .env.corpus-liturgicum ]]; then
  set -a
  source .env.corpus-liturgicum
  set +a
fi

source .venv/bin/activate
python manage.py runserver 127.0.0.1:8082
