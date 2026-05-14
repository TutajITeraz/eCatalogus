import json

from django.core.management.base import BaseCommand, CommandError

from etlapp.services import ETLImportConflictError, pull_remote_category, resolve_etl_peer


class Command(BaseCommand):
    help = 'Pulls an ETL category from a configured peer without using the GUI.'

    def add_arguments(self, parser):
        parser.add_argument('--peer', required=True, help='Peer id from ETL peer configuration, e.g. ecatalogus or mpl.')
        parser.add_argument('--category', choices=['main', 'shared'], required=True, help='ETL category to pull.')
        parser.add_argument('--since', help='Optional ISO datetime/date lower bound for incremental pull.')
        parser.add_argument(
            '--force-remote-uuid',
            action='append',
            dest='force_remote_uuids',
            help='UUID to force from remote side when resolving shared conflicts. Can be passed multiple times.',
        )
        parser.add_argument(
            '--keep-local-uuid',
            action='append',
            dest='keep_local_uuids',
            help='UUID to keep locally when resolving shared conflicts. Can be passed multiple times.',
        )

    def handle(self, *args, **options):
        try:
            peer = resolve_etl_peer(options['peer'])
            result = pull_remote_category(
                peer['url'],
                options['category'],
                since=options.get('since') or None,
                force_remote_uuids=options.get('force_remote_uuids') or [],
                keep_local_uuids=options.get('keep_local_uuids') or [],
            )
        except ETLImportConflictError as exc:
            raise CommandError(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2)) from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(json.dumps(result, ensure_ascii=False, indent=2)))