"""Reports local divergence in the `main` reference tables.

`main` is curated in eCatalogus and reaches every other instance through the
one-way ETL pull, so anything written locally is drift with one of two endings:
a row that also exists upstream gets silently overwritten by the next pull
(only `shared` has conflict detection), and a row created locally stays local
forever, because `main` has no push path.

This command answers "has anyone touched the vocabularies here?" from two
directions:

* against the peer — every local row is compared with the upstream export using
  the very same routine the importer uses, so `differs` means precisely "the
  next `Pull main dictionaries` would overwrite this row";
* locally — the Django admin log and the ETL deletion records name who changed
  what and when, which the peer diff cannot tell you.

The two are complementary: the admin log misses writes made through the iommi
admin or the bulk import endpoints, and the peer diff cannot attribute a
change to a person.
"""

import json
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from etlapp.model_categories import get_model_category
from etlapp.services import (
    _changed_fields,
    _get_category_models_in_dependency_order,
    _get_comparable_instance_value,
    _get_concrete_field,
    _get_peer_api_token,
    _normalize_peer_url,
    _prepare_import_values,
    _serialize_instance,
    fetch_remote_etl_json,
    get_etl_peer_configs,
    get_main_source_urls,
    resolve_etl_peer,
)


ACTION_LABELS = {ADDITION: 'added', CHANGE: 'changed', DELETION: 'deleted'}

MAX_VALUE_LENGTH = 120


def _format_value(value):
    text = 'NULL' if value is None else str(value)
    if len(text) > MAX_VALUE_LENGTH:
        text = f'{text[:MAX_VALUE_LENGTH - 1]}…'
    return text.replace('\t', ' ').replace('\n', ' ')


def _parse_since(raw):
    if not raw:
        return None

    parsed = parse_datetime(raw)
    if parsed is None:
        parsed_date = parse_date(raw)
        if parsed_date is not None:
            parsed = datetime.combine(parsed_date, datetime.min.time())

    if parsed is None:
        raise CommandError(f'Could not parse "{raw}" as an ISO date or datetime.')

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())

    return parsed


def _resolve_default_peer():
    """This instance's upstream — the peer it actually pulls `main` from.

    A configured peer is preferred over a bare ETL_MASTER_URL even when both
    name an upstream: only the configured one carries an API token. On limbo
    the two disagree (registry says mpl, the environment still says
    eCatalogus) and only mpl will authenticate.
    """
    allowed_urls = get_main_source_urls()
    if not allowed_urls:
        raise CommandError(
            'This instance has no upstream peer configured, so there is nothing to compare '
            'against. It is the source of truth for main. Pass --peer explicitly to audit '
            'a different instance from here, or --local-only to skip the comparison.'
        )

    for peer in get_etl_peer_configs():
        if _normalize_peer_url(peer['url']) in allowed_urls:
            return peer

    fallback_url = sorted(allowed_urls)[0]
    return {
        'id': 'upstream',
        'label': 'Upstream',
        'url': fallback_url,
        'api_token': _get_peer_api_token(fallback_url),
    }


def _select_models(requested_model_names):
    requested = set(requested_model_names or [])
    available = {
        model.__name__
        for model in apps.get_app_config('indexerapp').get_models()
        if get_model_category(model.__name__) == 'main'
    }

    unknown = requested.difference(available)
    if unknown:
        raise CommandError('Not main-category indexerapp models: ' + ', '.join(sorted(unknown)))

    models = [
        model for model in _get_category_models_in_dependency_order('main')
        if not requested or model.__name__ in requested
    ]
    return models


def _index_remote_payload(payload):
    """{model label: {uuid: record}} out of an ETL main export."""
    if not isinstance(payload, dict):
        raise CommandError('Peer returned an unexpected payload for the main export.')

    remote_by_model = {}
    for model_payload in payload.get('models') or []:
        model_label = model_payload.get('model')
        if not model_label:
            continue
        records = {}
        for record in model_payload.get('results') or []:
            record_uuid = record.get('uuid')
            if record_uuid:
                records[str(record_uuid)] = record
        remote_by_model[model_label] = records

    return remote_by_model


def _remote_label(model, attrs):
    """What the upstream row would be called, without saving anything.

    Used to spot a local row that duplicates an upstream one under a different
    uuid — the failure mode that produced three "XII 3/4" datings. __str__ can
    reach for related objects, so an unsaved instance may not be able to render
    itself; an unusable label simply never matches.
    """
    try:
        return str(model(**attrs))
    except Exception:
        return None


def _normalise_label(label):
    return ' '.join(str(label).split()).casefold() if label else None


def _compare_model_against_remote(model, remote_records):
    """Rows that the next pull would overwrite, and rows it would never see."""
    findings = {
        'local_only': [],
        'differs': [],
        'missing_uuid': 0,
        'unresolvable': [],
        'missing_locally': 0,
        'checked': 0,
    }

    seen_uuids = set()

    upstream_by_label = {}
    for remote_uuid, remote_record in remote_records.items():
        try:
            remote_attrs, _, _ = _prepare_import_values(model, remote_record)
        except ValueError:
            continue
        label_key = _normalise_label(_remote_label(model, remote_attrs))
        if label_key:
            upstream_by_label.setdefault(label_key, []).append({
                'uuid': remote_uuid,
                'label': _remote_label(model, remote_attrs),
            })

    for instance in model.objects.all().order_by('pk').iterator(chunk_size=500):
        findings['checked'] += 1
        instance_uuid = getattr(instance, 'uuid', None)

        if instance_uuid is None:
            findings['missing_uuid'] += 1
            continue

        instance_uuid = str(instance_uuid)
        seen_uuids.add(instance_uuid)
        remote_record = remote_records.get(instance_uuid)

        if remote_record is None:
            label = str(instance)
            findings['local_only'].append({
                'uuid': instance_uuid,
                'pk': instance.pk,
                'label': label,
                'upstream_matches': upstream_by_label.get(_normalise_label(label), []),
                'record': _serialize_instance(instance),
            })
            continue

        try:
            attrs, m2m_values, _ = _prepare_import_values(model, remote_record)
        except ValueError as exc:
            findings['unresolvable'].append({'uuid': instance_uuid, 'pk': instance.pk, 'reason': str(exc)})
            continue

        changed = _changed_fields(instance, attrs, m2m_values)
        if not changed:
            continue

        differences = []
        for field_name in changed:
            if field_name in m2m_values:
                differences.append({'field': field_name, 'local': '<m2m>', 'remote': '<m2m>'})
                continue
            differences.append({
                'field': field_name,
                'local': _format_value(_get_comparable_instance_value(instance, field_name)),
                'remote': _format_value(attrs.get(field_name)),
            })

        findings['differs'].append({
            'uuid': instance_uuid,
            'pk': instance.pk,
            'label': str(instance),
            'differences': differences,
        })

    findings['missing_locally'] = len(set(remote_records).difference(seen_uuids))
    return findings


def _collect_admin_log(models, since=None, limit=500):
    """Who changed a main vocabulary in the Django admin, and when."""
    content_types = ContentType.objects.filter(
        app_label='indexerapp',
        model__in=[model._meta.model_name for model in models],
    )
    queryset = LogEntry.objects.filter(content_type__in=content_types)
    if since is not None:
        queryset = queryset.filter(action_time__gte=since)

    total = queryset.count()
    entries = []
    for entry in queryset.select_related('user', 'content_type').order_by('-action_time')[:limit]:
        entries.append({
            'model': entry.content_type.model_class().__name__ if entry.content_type.model_class() else entry.content_type.model,
            'action': ACTION_LABELS.get(entry.action_flag, str(entry.action_flag)),
            'object_repr': entry.object_repr,
            'object_id': entry.object_id,
            'user': entry.user.get_username() if entry.user else 'unknown',
            'at': entry.action_time.isoformat(),
        })

    return {'total': total, 'listed': entries, 'truncated': total > len(entries)}


def _collect_local_deletions(since=None, limit=500):
    from indexerapp.models import DeletedRecord

    queryset = DeletedRecord.objects.filter(category='main')
    if since is not None:
        queryset = queryset.filter(deleted_at__gte=since)

    total = queryset.count()
    records = [
        {
            'model_label': record.model_label,
            'object_uuid': str(record.object_uuid),
            'deleted_at': record.deleted_at.isoformat(),
        }
        for record in queryset.order_by('-deleted_at')[:limit]
    ]
    return {'total': total, 'listed': records, 'truncated': total > len(records)}


class Command(BaseCommand):
    help = 'Reports rows in the main reference tables that diverge from the upstream instance.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--peer',
            help='Peer id to compare against. Defaults to this instance\'s parent peer.',
        )
        parser.add_argument(
            '--local-only',
            action='store_true',
            help='Skip the peer comparison; report only local evidence (admin log, deletions, rows without uuid).',
        )
        parser.add_argument(
            '--model',
            action='append',
            dest='models',
            help='Limit the audit to one main model. Can be passed multiple times.',
        )
        parser.add_argument(
            '--since',
            help='ISO date/datetime lower bound for the admin log and deletion listings.',
        )
        parser.add_argument(
            '--show',
            type=int,
            default=20,
            help='Maximum rows listed per model and per section. 0 lists everything. Default 20.',
        )
        parser.add_argument('--json', action='store_true', help='Emit the full report as JSON.')
        parser.add_argument('--output', help='Write every drifted row to this file as TSV.')
        parser.add_argument(
            '--export-local-only',
            help=(
                'Write the local-only rows to this path as an ETL main bundle, ready for '
                'import_etl_bundle on eCatalogus. UUIDs are preserved, so the rows come back '
                'matched at the next pull instead of duplicating.'
            ),
        )
        parser.add_argument(
            '--skip-duplicate-candidates',
            action='store_true',
            help='Leave rows that share a name with an upstream row out of the exported bundle.',
        )
        parser.add_argument(
            '--fail-on-drift',
            action='store_true',
            help='Exit with a command error when drift is found, for use in a cron check.',
        )

    def handle(self, *args, **options):
        since = _parse_since(options.get('since'))
        models = _select_models(options.get('models'))
        show = options['show']

        report = {
            'site_name': getattr(settings, 'SITE_NAME', ''),
            'instance': getattr(settings, 'ETL_SELF_PEER_ID', '') or getattr(settings, 'INSTANCE_SLUG', ''),
            'since': since.isoformat() if since else None,
            'peer': None,
            'models': [],
            'admin_log': _collect_admin_log(models, since),
            'local_deletions': _collect_local_deletions(since),
        }

        if options['local_only']:
            for model in models:
                report['models'].append({
                    'model': model._meta.label,
                    'name': model.__name__,
                    'checked': model.objects.count(),
                    'local_only': [],
                    'differs': [],
                    'unresolvable': [],
                    'missing_uuid': model.objects.filter(uuid__isnull=True).count(),
                    'missing_locally': 0,
                })
        else:
            peer = resolve_etl_peer(options['peer']) if options.get('peer') else _resolve_default_peer()
            report['peer'] = {'id': peer['id'], 'url': peer['url']}

            try:
                payload = fetch_remote_etl_json(
                    peer['url'],
                    '/api/etl/main/export/',
                    api_token=peer.get('api_token') or _get_peer_api_token(peer['url']),
                )
            except ValueError as exc:
                raise CommandError(f'Could not read the main export from {peer["url"]}: {exc}') from exc

            remote_by_model = _index_remote_payload(payload)

            for model in models:
                if _get_concrete_field(model, 'entry_date') is None:
                    # The exporter skips these, so the peer never sends them and
                    # every local row would look like drift.
                    continue

                findings = _compare_model_against_remote(model, remote_by_model.get(model._meta.label, {}))
                findings['model'] = model._meta.label
                findings['name'] = model.__name__
                report['models'].append(findings)

        drift_count = sum(
            len(entry['local_only']) + len(entry['differs']) + entry['missing_uuid'] + len(entry['unresolvable'])
            for entry in report['models']
        )
        report['drift_row_count'] = drift_count

        if options['export_local_only']:
            self._write_promotion_bundle(
                options['export_local_only'],
                report,
                skip_duplicate_candidates=options['skip_duplicate_candidates'],
            )

        if options['output']:
            self._write_tsv(options['output'], report)

        if options['json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            self._write_human_report(report, show, local_only=options['local_only'])

        if drift_count and options['fail_on_drift']:
            raise CommandError(f'Main reference data drift detected: {drift_count} row(s).')

        return None

    def _write_tsv(self, path, report):
        lines = ['model\tfinding\tuuid\tpk\tfield\tlocal\tremote_or_upstream_uuid\tlabel']
        for entry in report['models']:
            for row in entry['local_only']:
                finding = 'duplicate_candidate' if row.get('upstream_matches') else 'local_only'
                upstream = ' '.join(match['uuid'] for match in row.get('upstream_matches') or [])
                lines.append(
                    f'{entry["model"]}\t{finding}\t{row["uuid"]}\t{row["pk"]}\t\t\t{upstream}\t{_format_value(row["label"])}'
                )
            for row in entry['differs']:
                for difference in row['differences']:
                    lines.append(
                        f'{entry["model"]}\tdiffers\t{row["uuid"]}\t{row["pk"]}\t'
                        f'{difference["field"]}\t{difference["local"]}\t{difference["remote"]}\t{_format_value(row["label"])}'
                    )
            for row in entry['unresolvable']:
                lines.append(f'{entry["model"]}\tunresolvable\t{row["uuid"]}\t{row["pk"]}\t\t\t\t{_format_value(row["reason"])}')

        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(lines) + '\n')

        self.stdout.write(f'Wrote {len(lines) - 1} drift row(s) to {path}')

    def _write_promotion_bundle(self, path, report, skip_duplicate_candidates):
        """An ETL main bundle of the local-only rows, for import on eCatalogus.

        The serialised records keep their uuids, so once eCatalogus has them the
        next pull matches these very rows instead of adding a second copy beside
        them — and every local manuscript that already points at them keeps
        pointing at them.
        """
        models_payload = []
        record_count = 0
        skipped = 0

        for entry in report['models']:
            records = []
            for row in entry['local_only']:
                if skip_duplicate_candidates and row.get('upstream_matches'):
                    skipped += 1
                    continue
                records.append(row['record'])

            if records:
                models_payload.append({'model': entry['model'], 'results': records})
                record_count += len(records)

        payload = {
            'site_name': report['site_name'],
            'category': 'main',
            'model_count': len(models_payload),
            'record_count': record_count,
            'models': models_payload,
        }

        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.write('\n')

        message = f'Wrote {record_count} local-only row(s) across {len(models_payload)} model(s) to {path}'
        if skipped:
            message += f' ({skipped} duplicate candidate(s) left out)'
        self.stdout.write(message)

    def _write_human_report(self, report, show, local_only):
        def limited(rows):
            return rows if show == 0 else rows[:show]

        self.stdout.write(f'Instance: {report["site_name"]} ({report["instance"] or "unnamed"})')

        if local_only:
            self.stdout.write('Peer comparison skipped (--local-only).')
        else:
            self.stdout.write(f'Compared against: {report["peer"]["id"]} {report["peer"]["url"]}')

        for entry in report['models']:
            issues = (
                len(entry['local_only']) + len(entry['differs'])
                + entry['missing_uuid'] + len(entry['unresolvable'])
            )
            if not issues:
                continue

            duplicate_candidates = sum(1 for row in entry['local_only'] if row.get('upstream_matches'))
            self.stdout.write(
                f'{entry["name"]}: status=DRIFT checked={entry["checked"]} '
                f'local_only={len(entry["local_only"])} duplicate_candidates={duplicate_candidates} '
                f'differs={len(entry["differs"])} '
                f'missing_uuid={entry["missing_uuid"]} unresolvable={len(entry["unresolvable"])} '
                f'missing_locally={entry["missing_locally"]}'
            )

            for row in limited(entry['local_only']):
                self.stdout.write(f'  local-only  uuid={row["uuid"]} pk={row["pk"]} {_format_value(row["label"])}')
                for match in row.get('upstream_matches') or []:
                    self.stdout.write(
                        f'      duplicate? upstream {match["uuid"]} already has this name'
                    )
            for row in limited(entry['differs']):
                self.stdout.write(f'  differs     uuid={row["uuid"]} pk={row["pk"]} {_format_value(row["label"])}')
                for difference in row['differences']:
                    self.stdout.write(
                        f'      {difference["field"]}: local={difference["local"]!r} remote={difference["remote"]!r}'
                    )
            for row in limited(entry['unresolvable']):
                self.stdout.write(f'  unresolvable uuid={row["uuid"]} pk={row["pk"]} {_format_value(row["reason"])}')

        admin_log = report['admin_log']
        if admin_log['total']:
            self.stdout.write(
                f'Admin log entries touching main models: {admin_log["total"]}'
                + (f' (listing {min(show, len(admin_log["listed"])) if show else len(admin_log["listed"])})' if admin_log['total'] > 1 else '')
            )
            for entry in limited(admin_log['listed']):
                self.stdout.write(
                    f'  {entry["at"]} {entry["user"]} {entry["action"]} {entry["model"]} {_format_value(entry["object_repr"])}'
                )
        else:
            self.stdout.write('Admin log entries touching main models: none')

        deletions = report['local_deletions']
        if deletions['total']:
            self.stdout.write(f'Local main deletions recorded: {deletions["total"]}')
            for entry in limited(deletions['listed']):
                self.stdout.write(f'  {entry["deleted_at"]} {entry["model_label"]} uuid={entry["object_uuid"]}')

        if report['drift_row_count']:
            self.stdout.write(self.style.WARNING(f'Drift found: {report["drift_row_count"]} row(s).'))
        elif local_only:
            self.stdout.write(self.style.SUCCESS('No local evidence of main edits.'))
        else:
            self.stdout.write(self.style.SUCCESS('No drift: every local main row matches the peer.'))
