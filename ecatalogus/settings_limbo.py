"""Instance settings for MPL Limbo. Safe to commit; secrets live in .env.limbo."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug="limbo",
    defaults={
        "site_name": "MPL Limbo",
        "domain": "limbo.monumenta-poloniae-liturgica.ispan.pl",
        "overlay_dir": "static_limbo",
        "database_name": "limbo",
        "database_user": "ecatalogus_user",
        "project_id": 2,
        "foreign_id_name": "MSPL no.",
        "role": "slave",
        "peer_id": "limbo",
        "canonical_master_id": "ecatalogus",
        "default_parent_peer": "mpl",
        "source_peers": ['mpl'],
        "public_url": "https://limbo.monumenta-poloniae-liturgica.ispan.pl",
        "allowed_hosts": ['limbo.monumenta-poloniae-liturgica.ispan.pl', '127.0.0.1', 'localhost'],
        "csrf_trusted_origins": ['https://limbo.monumenta-poloniae-liturgica.ispan.pl', 'http://limbo.monumenta-poloniae-liturgica.ispan.pl', 'https://127.0.0.1', 'http://127.0.0.1'],
        "cors_allowed_origins": ['http://localhost:3000', 'http://localhost:8000', 'https://limbo.monumenta-poloniae-liturgica.ispan.pl', 'http://limbo.monumenta-poloniae-liturgica.ispan.pl'],
    },
)
