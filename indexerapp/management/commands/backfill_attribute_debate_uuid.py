import uuid

from django.core.management.base import BaseCommand

from indexerapp.models import AttributeDebate


class Command(BaseCommand):
    help = 'Populate AttributeDebate.uuid for legacy rows that still have no own UUID.'

    def handle(self, *args, **options):
        updated = 0

        for debate in AttributeDebate.objects.filter(uuid__isnull=True).only('pk', 'uuid').iterator():
            debate.uuid = uuid.uuid4()
            debate.save(update_fields=['uuid'])
            updated += 1

        if updated == 0:
            self.stdout.write(self.style.SUCCESS('No legacy AttributeDebate rows require uuid backfill.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Backfilled {updated} AttributeDebate UUID rows.'))