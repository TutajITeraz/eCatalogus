from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Populate attribute_debate.object_uuid from legacy object_id rows before removing object_id.'

    def handle(self, *args, **options):
        if not self._object_id_column_exists():
            self.stdout.write(self.style.WARNING('attribute_debate.object_id column is already absent; nothing to backfill.'))
            return

        rows = self._load_legacy_rows()
        if not rows:
            self.stdout.write(self.style.SUCCESS('No legacy AttributeDebate rows require object_uuid backfill.'))
            return

        content_type_ids = {row['content_type_id'] for row in rows}
        content_types = ContentType.objects.in_bulk(content_type_ids)

        updated = 0
        skipped = 0

        with transaction.atomic(), connection.cursor() as cursor:
            for row in rows:
                content_type = content_types.get(row['content_type_id'])
                model_class = content_type.model_class() if content_type is not None else None
                if model_class is None or not hasattr(model_class, 'uuid'):
                    skipped += 1
                    continue

                object_uuid = model_class.objects.filter(pk=row['object_id']).values_list('uuid', flat=True).first()
                if object_uuid is None:
                    skipped += 1
                    continue

                db_uuid_value = connection.ops.adapt_uuidfield_value(object_uuid)
                cursor.execute(
                    'UPDATE attribute_debate SET object_uuid = %s WHERE id = %s',
                    [db_uuid_value, row['id']],
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Backfilled {updated} AttributeDebate rows.'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped} rows without a resolvable UUID target.'))

    def _object_id_column_exists(self):
        with connection.cursor() as cursor:
            columns = {
                description.name
                for description in connection.introspection.get_table_description(cursor, 'attribute_debate')
            }
        return 'object_id' in columns

    def _load_legacy_rows(self):
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT id, content_type_id, object_id FROM attribute_debate WHERE object_uuid IS NULL AND object_id IS NOT NULL'
            )
            return [
                {'id': row[0], 'content_type_id': row[1], 'object_id': row[2]}
                for row in cursor.fetchall()
            ]