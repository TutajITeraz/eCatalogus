import json

from django.core.management.base import BaseCommand, CommandError

from etlapp.services import pull_remote_manuscript, resolve_etl_peer


class Command(BaseCommand):
    help = 'Pulls one manuscript ETL package from a configured peer without using the GUI.'

    def add_arguments(self, parser):
        parser.add_argument('--peer', required=True, help='Peer id from ETL peer configuration, e.g. master or slave-1.')
        parser.add_argument('--manuscript-uuid', required=True, help='UUID of the manuscript package to pull.')

    def handle(self, *args, **options):
        try:
            peer = resolve_etl_peer(options['peer'])
            result = pull_remote_manuscript(peer['url'], options['manuscript_uuid'])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(json.dumps(result, ensure_ascii=False, indent=2)))