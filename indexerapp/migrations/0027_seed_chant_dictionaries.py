"""Load ChantMode (68 Cantus mode codes) and ChantDifferentia (1279 Differentiae Database entries).

Runs on every instance, so the UUIDs are derived from the short name rather than
random: the same code gets the same UUID everywhere and the ETL pull of the
``main`` dictionaries matches rows instead of colliding on ``short_name``.

Idempotent: existing rows (found by ``short_name``) are updated in place and keep
their UUID. The data files live in ``indexerapp/data/cantus``; the differentiae
come with their own licence (CC BY-NC-SA 4.0), see the LICENSE file there.
"""

import csv
from pathlib import Path

from django.db import migrations

from etlapp.uuid_utils import build_deterministic_sync_uuid


DATA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'cantus'


def _rows(filename):
    with open(DATA_DIR / filename, newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def _upsert(model, label, short_name, values):
    instance = model.objects.filter(short_name=short_name).first()
    if instance is None:
        instance = model(short_name=short_name)
    if instance.uuid is None:
        instance.uuid = build_deterministic_sync_uuid(label, short_name)
    for name, value in values.items():
        setattr(instance, name, value)
    instance.save()
    return instance


def seed(apps, schema_editor):
    ChantMode = apps.get_model('indexerapp', 'ChantMode')
    ChantDifferentia = apps.get_model('indexerapp', 'ChantDifferentia')

    modes = {}
    for row in _rows('chant_modes.tsv'):
        modes[row['short_name']] = _upsert(
            ChantMode, 'indexerapp.ChantMode', row['short_name'], {'name': row['name']},
        )

    for row in _rows('07_differentiae_database.tsv'):
        mode = row['mode'].strip()
        other_mode = row['other_mode']
        if mode == 'P':
            mode, other_mode = '', other_mode or 'Tonus peregrinus'
        _upsert(ChantDifferentia, 'indexerapp.ChantDifferentia', row['differentia_id'], {
            'chant_mode_uuid': modes[mode] if mode else None,
            'other_mode': other_mode,
            'melodic_transcription': row['melodic_transcription'],
            'saeculorum': row['saeculorum'],
            'amen': row['amen'],
            'source_url': row['url'],
        })


class Migration(migrations.Migration):

    dependencies = [
        ('indexerapp', '0026_chant_mode_differentia_content_fields'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
