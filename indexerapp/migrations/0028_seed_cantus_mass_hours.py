"""Add the two unspecified MassHour rows Cantus Index needs: MASS and D.

Cantus marks 13 699 chants only as ``MASS`` (no M1/M2/M3) and 93 only as ``D``
("Day Hours", no Prime/Terce/Sext/None). Without these rows the import would
drop the office. Same kind of entry as "Vespers (single)" and "Compline (single)".

Runs on every instance, so, as in 0027, the UUID is derived from the short name
(the existing rows use the legacy pk, which a new row does not have). The type
is linked only where that Type row exists. Idempotent: an existing row with the
same short name is updated and keeps its UUID.
"""

from django.db import migrations

from etlapp.uuid_utils import build_deterministic_sync_uuid


MASS_TYPE_UUID = '55c19bba-2c11-5dfa-8e6a-53006539eca4'
OFFICE_TYPE_UUID = 'd73421c6-ff78-5b2d-bfcd-c20d72c54082'

MASS_HOURS = (
    ('MASS', 'Mass (unspecified)', MASS_TYPE_UUID),
    ('D', 'Day Hours (unspecified)', OFFICE_TYPE_UUID),
)


def seed(apps, schema_editor):
    MassHour = apps.get_model('indexerapp', 'MassHour')
    Type = apps.get_model('indexerapp', 'Type')

    for short_name, name, type_uuid in MASS_HOURS:
        instance = MassHour.objects.filter(short_name=short_name).first()
        if instance is None:
            instance = MassHour(short_name=short_name)
        if instance.uuid is None:
            instance.uuid = build_deterministic_sync_uuid('indexerapp.MassHour', short_name)
        instance.name = name
        instance.type_uuid = Type.objects.filter(uuid=type_uuid).first()
        instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('indexerapp', '0027_seed_chant_dictionaries'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
