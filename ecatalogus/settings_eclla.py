"""Instance settings for eCLLA. Safe to commit; secrets live in .env.eclla."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug="eclla",
    defaults={
        "site_name": "eCLLA",
        "domain": "api.eclla.ecatalogus.ispan.pl",
        "overlay_dir": "static_eclla",
        "database_name": "eclla",
        "database_user": "ecatalogus_user",
        "project_id": 1,
        "foreign_id_name": "CLLA no.",
        "role": "slave",
        "peer_id": "eclla",
        "canonical_master_id": "ecatalogus",
        "default_parent_peer": "ecatalogus",
        "source_peers": ['ecatalogus'],
        "public_url": "https://api.eclla.ecatalogus.ispan.pl",
        "allowed_hosts": ['api.eclla.ecatalogus.ispan.pl', '127.0.0.1', 'localhost'],
        "csrf_trusted_origins": ['https://api.eclla.ecatalogus.ispan.pl', 'http://api.eclla.ecatalogus.ispan.pl', 'https://eclla.henrybradshawsociety.org', 'https://127.0.0.1', 'http://127.0.0.1'],
        "cors_allowed_origins": ['http://localhost:3000', 'http://localhost:8000', 'https://api.eclla.ecatalogus.ispan.pl', 'http://api.eclla.ecatalogus.ispan.pl', 'https://eclla.henrybradshawsociety.org'],
        # The public UI is hosted as static files on eclla.henrybradshawsociety.org
        # and calls this API cross-origin.
        "api_integration_origins": [
            "https://eclla.henrybradshawsociety.org",
        ],
    },
)
