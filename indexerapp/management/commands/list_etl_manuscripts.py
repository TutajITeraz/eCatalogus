import json

from django.core.management.base import BaseCommand, CommandError

from etlapp.services import fetch_remote_etl_json, resolve_etl_peer


class Command(BaseCommand):
    help = 'Lists remote manuscripts available for ETL pull from a configured peer.'

    def add_arguments(self, parser):
        parser.add_argument('--peer', required=True, help='Peer id from ETL peer configuration, e.g. master or slave-1.')

    def handle(self, *args, **options):
        try:
            peer = resolve_etl_peer(options['peer'])
            payload = fetch_remote_etl_json(
                peer['url'],
                '/api/etl/manuscripts/list/',
                api_token=peer.get('api_token'),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(json.dumps(payload, ensure_ascii=False, indent=2)))