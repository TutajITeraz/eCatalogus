"""Instance settings for eCatalogus. Safe to commit; secrets live in .env."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug='ecatalogus',
    defaults={
        'site_name': 'eCatalogus',
        'domain': 'ecatalogus.ispan.pl',
        'overlay_dir': 'static_ecatalogus',
        'database_name': 'ecatalogus',
        'database_user': 'ecatalogus_user',
        'project_id': 0,
        'foreign_id_name': 'foreign id',
        'role': 'master',
        'peer_id': 'ecatalogus',
        'source_peers': ['mpl'],
        'public_url': 'https://ecatalogus.ispan.pl',
        'allowed_hosts': [
            'ecatalogus.ispan.pl',
            '127.0.0.1',
            'localhost',
        ],
        'csrf_trusted_origins': [
            'https://ecatalogus.ispan.pl',
            'http://ecatalogus.ispan.pl',
            'https://127.0.0.1',
            'http://127.0.0.1',
        ],
        'cors_allowed_origins': [
            'http://localhost:3000',
            'http://localhost:8000',
            'https://ecatalogus.ispan.pl',
            'http://ecatalogus.ispan.pl',
        ],
    },
)
