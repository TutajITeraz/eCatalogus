# Split out from the FK-constraint migration: MySQL cannot alter/drop an index
# that already backs a foreign key constraint, so the target columns must
# become unique *before* any FK in a later migration references them via
# to_field='uuid' with a real db_constraint.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('indexerapp', '0017_remove_binding_data_contributor_remove_binding_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='manuscripts',
            name='uuid',
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='projects',
            name='uuid',
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
    ]
