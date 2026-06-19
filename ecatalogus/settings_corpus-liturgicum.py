"""Instance settings for Corpus Liturgicum. Safe to commit; secrets live in .env.corpus-liturgicum."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug="corpus-liturgicum",
    defaults={
        "site_name": "Corpus Liturgicum",
        "domain": "corpus-liturgicum.org",
        "overlay_dir": "static_corpus-liturgicum",
        "database_name": "corpus-liturgicum",
        "database_user": "ecatalogus_user",
        "project_id": 5,
        "foreign_id_name": "foreign id",
        "role": "slave",
        "peer_id": "corpus-liturgicum",
        "canonical_master_id": "ecatalogus",
        "default_parent_peer": "ecatalogus",
        "source_peers": ['ecatalogus'],
        "public_url": "https://corpus-liturgicum.org",
        "allowed_hosts": ['corpus-liturgicum.org', '127.0.0.1', 'localhost'],
        "csrf_trusted_origins": ['https://corpus-liturgicum.org', 'http://corpus-liturgicum.org', 'https://127.0.0.1', 'http://127.0.0.1'],
        "cors_allowed_origins": ['http://localhost:3000', 'http://localhost:8000', 'https://corpus-liturgicum.org', 'http://corpus-liturgicum.org'],
    },
)
