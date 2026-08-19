"""Folds a duplicated `main` row into the canonical one and removes it.

When an editor adds a vocabulary entry locally instead of reusing the one that
came down from eCatalogus, the result is two rows for one thing: the canonical
one and a local twin that will never travel anywhere. Deleting the twin is not
enough — every reference to `main` is `on_delete=PROTECT`, so the delete is
refused until the manuscripts, origins, provenances and datings that point at
it are repointed at the canonical row. That repointing is what this command
does, in one transaction, before the delete.

It is a maintenance command on purpose: the read-only guard closes the editorial
surfaces on a slave instance, and this operation could not be done through them
anyway — the admin would only answer with a ProtectedError.

Nothing is written without --apply.
"""

import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from etlapp.model_categories import get_model_category


def _iter_main_models():
    for model in apps.get_app_config('indexerapp').get_models():
        if get_model_category(model.__name__) == 'main':
            yield model


def _find_by_uuid(uuid_value):
    """The main-category row carrying this uuid, whichever table it lives in."""
    for model in _iter_main_models():
        try:
            instance = model.objects.filter(uuid=uuid_value).first()
        except (ValueError, TypeError) as exc:
            raise CommandError(f'"{uuid_value}" is not a valid uuid: {exc}') from exc
        if instance is not None:
            return model, instance
    return None, None


def _parse_pairs(pair_arguments, pairs_file):
    pairs = []

    for raw in pair_arguments or []:
        if '=' not in raw:
            raise CommandError(f'--pair expects <duplicate-uuid>=<canonical-uuid>, got "{raw}".')
        duplicate_uuid, canonical_uuid = raw.split('=', 1)
        pairs.append((duplicate_uuid.strip(), canonical_uuid.strip()))

    if pairs_file:
        try:
            with open(pairs_file, 'r', encoding='utf-8') as handle:
                for line_number, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.replace('=', '\t').replace(',', '\t').split('\t')
                    parts = [part.strip() for part in parts if part.strip()]
                    if len(parts) < 2:
                        raise CommandError(f'{pairs_file}:{line_number}: expected two uuids, got "{line}".')
                    pairs.append((parts[0], parts[1]))
        except FileNotFoundError as exc:
            raise CommandError(f'Pairs file not found: {pairs_file}') from exc

    if not pairs:
        raise CommandError('Nothing to merge: pass --pair or --file.')

    return pairs


def _collect_references(model, instance):
    """Every row pointing at `instance`, grouped by the relation that points."""
    references = []

    for relation in model._meta.related_objects:
        related_model = relation.related_model
        field_name = relation.field.name

        if relation.many_to_many:
            queryset = related_model.objects.filter(**{field_name: instance})
            references.append({
                'kind': 'm2m',
                'model': related_model._meta.label,
                'field': field_name,
                'count': queryset.count(),
                'relation': relation,
            })
            continue

        queryset = related_model.objects.filter(**{field_name: instance})
        references.append({
            'kind': 'fk',
            'model': related_model._meta.label,
            'field': field_name,
            'count': queryset.count(),
            'relation': relation,
        })

    return [reference for reference in references if reference['count']]


def _repoint(reference, duplicate, canonical):
    relation = reference['relation']
    related_model = relation.related_model
    field_name = relation.field.name

    if reference['kind'] == 'm2m':
        moved = 0
        for holder in related_model.objects.filter(**{field_name: duplicate}):
            manager = getattr(holder, field_name)
            manager.remove(duplicate)
            manager.add(canonical)
            moved += 1
        return moved

    return related_model.objects.filter(**{field_name: duplicate}).update(**{field_name: canonical})


class Command(BaseCommand):
    help = 'Repoints every reference from a duplicated main row to the canonical one, then deletes the duplicate.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pair',
            action='append',
            dest='pairs',
            help='<duplicate-uuid>=<canonical-uuid>. Can be passed multiple times.',
        )
        parser.add_argument(
            '--file',
            dest='pairs_file',
            help='File with one "<duplicate-uuid> <canonical-uuid>" pair per line (tab, comma or = separated).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually repoint and delete. Without it the command only reports what it would do.',
        )
        parser.add_argument('--json', action='store_true', help='Emit the plan or result as JSON.')

    def handle(self, *args, **options):
        pairs = _parse_pairs(options.get('pairs'), options.get('pairs_file'))
        apply_changes = options['apply']

        plan = []

        for duplicate_uuid, canonical_uuid in pairs:
            if duplicate_uuid == canonical_uuid:
                raise CommandError(f'Duplicate and canonical uuid are the same: {duplicate_uuid}')

            duplicate_model, duplicate = _find_by_uuid(duplicate_uuid)
            if duplicate is None:
                raise CommandError(f'No main-category row found with uuid {duplicate_uuid}.')

            canonical_model, canonical = _find_by_uuid(canonical_uuid)
            if canonical is None:
                raise CommandError(f'No main-category row found with uuid {canonical_uuid}.')

            if duplicate_model is not canonical_model:
                raise CommandError(
                    f'Refusing to merge across tables: {duplicate_uuid} is a '
                    f'{duplicate_model.__name__} but {canonical_uuid} is a {canonical_model.__name__}.'
                )

            references = _collect_references(duplicate_model, duplicate)
            plan.append({
                'model': duplicate_model._meta.label,
                'duplicate': {'uuid': duplicate_uuid, 'pk': duplicate.pk, 'label': str(duplicate)},
                'canonical': {'uuid': canonical_uuid, 'pk': canonical.pk, 'label': str(canonical)},
                'references': references,
                'reference_count': sum(reference['count'] for reference in references),
                'instances': (duplicate_model, duplicate, canonical),
            })

        if apply_changes:
            self._apply(plan)

        return self._report(plan, apply_changes, options['json'])

    def _apply(self, plan):
        with transaction.atomic():
            for entry in plan:
                _, duplicate, canonical = entry['instances']
                moved = 0
                for reference in entry['references']:
                    moved += _repoint(reference, duplicate, canonical)
                entry['repointed'] = moved

                # Now that nothing PROTECTs it, the row can go. The pre_delete
                # signal records it as an ETL deletion, which is correct: this
                # instance really does not have that row any more.
                duplicate.delete()
                entry['deleted'] = True

    def _report(self, plan, applied, as_json):
        serialisable = []
        for entry in plan:
            serialisable.append({
                'model': entry['model'],
                'duplicate': entry['duplicate'],
                'canonical': entry['canonical'],
                'references': [
                    {
                        'kind': reference['kind'],
                        'model': reference['model'],
                        'field': reference['field'],
                        'count': reference['count'],
                    }
                    for reference in entry['references']
                ],
                'reference_count': entry['reference_count'],
                'repointed': entry.get('repointed', 0),
                'deleted': entry.get('deleted', False),
            })

        if as_json:
            self.stdout.write(json.dumps({'applied': applied, 'merges': serialisable}, ensure_ascii=False, indent=2))
            return None

        for entry in serialisable:
            verb = 'merged' if applied else 'would merge'
            self.stdout.write(
                f'{entry["model"]}: {verb} {entry["duplicate"]["label"]} '
                f'({entry["duplicate"]["uuid"]}) into {entry["canonical"]["label"]} '
                f'({entry["canonical"]["uuid"]}) — {entry["reference_count"]} reference(s)'
            )
            for reference in entry['references']:
                self.stdout.write(
                    f'  {reference["kind"]:4} {reference["model"]}.{reference["field"]}: {reference["count"]}'
                )

        total = sum(entry['reference_count'] for entry in serialisable)
        if applied:
            self.stdout.write(self.style.SUCCESS(
                f'Merged {len(serialisable)} duplicate(s), repointed {total} reference(s).'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'Dry run: {len(serialisable)} duplicate(s) and {total} reference(s) would change. '
                f'Re-run with --apply to commit.'
            ))

        return None
