"""Instance settings for Canon Missae. Safe to commit; secrets live in .env.canon-missae."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug="canon-missae",
    defaults={
        "site_name": "Canon Missae",
        "domain": "canon-missae.ispan.pl",
        "overlay_dir": "static_canon-missae",
        "database_name": "canon-missae",
        "database_user": "ecatalogus_user",
        "project_id": 4,
        "foreign_id_name": "foreign id",
        "role": "slave",
        "peer_id": "canon-missae",
        "canonical_master_id": "ecatalogus",
        "default_parent_peer": "ecatalogus",
        "source_peers": ['ecatalogus'],
        "public_url": "https://canon-missae.ispan.pl",
        "allowed_hosts": ['canon-missae.ispan.pl', '127.0.0.1', 'localhost'],
        "csrf_trusted_origins": ['https://canon-missae.ispan.pl', 'http://canon-missae.ispan.pl', 'https://127.0.0.1', 'http://127.0.0.1'],
        "cors_allowed_origins": ['http://localhost:3000', 'http://localhost:8000', 'https://canon-missae.ispan.pl', 'http://canon-missae.ispan.pl'],
    },
)
