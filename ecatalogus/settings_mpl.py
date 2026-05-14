"""Instance settings for Liturgica Poloniae (MPL). Safe to commit; secrets live in .env."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug='mpl',
    defaults={
        'site_name': 'Liturgica Poloniae',
        'domain': 'monumenta-poloniae-liturgica.ispan.pl',
        'overlay_dir': 'static_mpl',
        'database_name': 'ispan_mpl',
        'database_user': 'ispan_mpl',
        'project_id': 2,
        'foreign_id_name': 'MSPL no.',
        'role': 'slave',
        'peer_id': 'mpl',
        'default_parent_peer': 'ecatalogus',
        'source_peers': ['ecatalogus'],
        'public_url': 'https://monumenta-poloniae-liturgica.ispan.pl',
        'allowed_hosts': [
            'monumenta-poloniae-liturgica.ispan.pl',
            'indexer.rebold.hostline.net.pl',
            'server.hostline.pl',
            'eclla.hostline.net.pl',
            '127.0.0.1',
            'localhost',
        ],
        'csrf_trusted_origins': [
            'https://monumenta-poloniae-liturgica.ispan.pl',
            'http://monumenta-poloniae-liturgica.ispan.pl',
            'https://indexer.rebold.hostline.net.pl',
            'http://indexer.rebold.hostline.net.pl',
            'https://eclla.hostline.net.pl',
            'http://eclla.hostline.net.pl',
            'https://lp.hostline.net.pl',
            'http://lp.hostline.net.pl',
            'https://liturgicapoloniae.hostline.net.pl',
            'http://liturgicapoloniae.hostline.net.pl',
            'https://127.0.0.1',
            'http://127.0.0.1',
        ],
        'cors_allowed_origins': [
            'http://localhost:3000',
            'http://indexer.rebold.hostline.net.pl',
            'https://indexer.rebold.hostline.net.pl',
            'https://polona.pl',
            'https://collections.library.yale.edu',
            'http://polona.pl',
            'http://collections.library.yale.edu',
            'http://eclla.hostline.net.pl',
            'https://eclla.hostline.net.pl',
            'http://lp.hostline.net.pl',
            'https://lp.hostline.net.pl',
            'http://liturgicapoloniae.hostline.net.pl',
            'https://liturgicapoloniae.hostline.net.pl',
            'http://monumenta-poloniae-liturgica.ispan.pl',
            'https://monumenta-poloniae-liturgica.ispan.pl',
        ],
    },
)
