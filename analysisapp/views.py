"""HTTP surface for the corpus analysis.

Reading is separated from computing. These endpoints hand over artifacts that a
run already wrote; none of them computes anything. Starting a run is the one
expensive operation and is guarded accordingly.
"""

import json
import os
import uuid as uuid_module

from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from indexerapp.api_access import user_can_write_api
from indexerapp.models import Content, Formulas

from .models import AnalysisArtifact, AnalysisRun
from .pipeline import DEFAULT_PARAMS

#: Artifacts served as text rather than JSON, for tools outside the browser.
TEXT_KINDS = {'nexus', 'newick'}


def _run_payload(run: AnalysisRun, include_artifacts: bool = False) -> dict:
    payload = {
        'uuid': str(run.uuid),
        'status': run.status,
        'progress': run.progress,
        'stage': run.stage,
        'pipeline_version': run.pipeline_version,
        'created_at': run.created_at.isoformat(),
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        'params': run.params,
        'summary': run.summary,
        'error': run.error,
    }
    if include_artifacts:
        payload['artifacts'] = [
            {
                'cohort': artifact.cohort,
                'cohort_label': artifact.cohort_label,
                'kind': artifact.kind,
                'size_bytes': artifact.size_bytes,
                'meta': artifact.meta,
            }
            for artifact in run.artifacts.all()
        ]
    return payload


class AnalysisRunListView(View):
    """Runs, newest first, so the page can offer a picker."""

    def get(self, request, *args, **kwargs):
        limit = min(int(request.GET.get('limit', 25)), 100)
        status = request.GET.get('status')

        runs = AnalysisRun.objects.all()
        if status:
            runs = runs.filter(status=status)

        return JsonResponse({
            'runs': [_run_payload(run) for run in runs[:limit]],
            'can_start': user_can_write_api(request.user),
            'defaults': {k: v for k, v in DEFAULT_PARAMS.items() if k != 'manuscript_uuids'},
        })


class AnalysisRunDetailView(View):
    """Status and artifact index for one run. Polled while a run is in progress."""

    def get(self, request, run_uuid, *args, **kwargs):
        try:
            run = AnalysisRun.objects.prefetch_related('artifacts').get(uuid=run_uuid)
        except AnalysisRun.DoesNotExist:
            raise Http404('No such analysis run.')
        return JsonResponse(_run_payload(run, include_artifacts=True))


class AnalysisManuscriptListView(View):
    """Everything that could go into a run, so a reader can pick what does.

    Served separately from the runs themselves because it describes the catalogue
    as it stands now, not what some past run happened to cover, and because the
    page only needs it when someone opens the picker.
    """

    def get(self, request, *args, **kwargs):
        from .extract import DEFAULT_MIN_ITEMS, summarize_manuscripts

        payload = summarize_manuscripts()
        payload['default_min_items'] = DEFAULT_MIN_ITEMS
        return JsonResponse(payload)


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisRunStartView(View):
    """Queue a run, falling back to running it inline when Celery is unavailable."""

    def post(self, request, *args, **kwargs):
        if not user_can_write_api(request.user):
            return JsonResponse(
                {'detail': 'Starting an analysis run requires an editorial account.'},
                status=403,
            )

        try:
            body = json.loads(request.body or b'{}')
        except ValueError:
            return JsonResponse({'detail': 'Malformed JSON body.'}, status=400)

        params = {}
        for key in ('min_items', 'min_manuscripts', 'min_block_support', 'min_cluster_size'):
            if key in body:
                try:
                    params[key] = int(body[key])
                except (TypeError, ValueError):
                    return JsonResponse({'detail': f'{key} must be an integer.'}, status=400)
        if body.get('manuscript_uuids'):
            params['manuscript_uuids'] = [str(u) for u in body['manuscript_uuids']]

        run = AnalysisRun.objects.create(
            params=params,
            created_by=request.user if request.user.is_authenticated else None,
        )

        queued, detail = self._dispatch(run)
        return JsonResponse({
            'run': _run_payload(run),
            'queued': queued,
            'detail': detail,
        }, status=202 if queued else 200)

    def _dispatch(self, run):
        from django.conf import settings

        from .tasks import run_corpus_analysis_task

        if getattr(settings, 'ANALYSIS_USE_CELERY', getattr(settings, 'ETL_USE_CELERY', True)):
            try:
                queue = getattr(settings, 'CELERY_TASK_DEFAULT_QUEUE', 'celery')
                run_corpus_analysis_task.apply_async([str(run.uuid)], queue=queue)
                return True, 'Run queued.'
            except Exception as exc:
                # No broker reachable. Better to block this one request than to
                # leave a run sitting in "pending" for ever with no worker.
                detail = f'Celery unavailable ({exc}); ran synchronously.'
        else:
            detail = 'Celery disabled; ran synchronously.'

        from .pipeline import execute_run
        try:
            execute_run(run)
        except Exception as exc:
            return False, f'{detail} The run failed: {exc}'
        return False, detail


class AnalysisArtifactView(View):
    """Serve one precomputed artifact.

    The file path comes from the database record, never from the request, so a
    cohort or kind crafted by a caller cannot walk out of the run's directory.
    """

    def get(self, request, run_uuid, cohort, kind, *args, **kwargs):
        try:
            artifact = AnalysisArtifact.objects.select_related('run').get(
                run__uuid=run_uuid, cohort=cohort, kind=kind,
            )
        except AnalysisArtifact.DoesNotExist:
            raise Http404('No such artifact.')

        path = artifact.absolute_path
        if not os.path.exists(path):
            raise Http404('Artifact file is missing from storage.')

        if kind in TEXT_KINDS:
            response = FileResponse(
                open(path, 'rb'), content_type='text/plain; charset=utf-8',
            )
            response['Content-Disposition'] = (
                f'attachment; filename="{os.path.basename(path)}"'
            )
            return response

        response = FileResponse(open(path, 'rb'), content_type='application/json')
        # Artifacts are immutable once written, so they can be cached hard.
        response['Cache-Control'] = 'public, max-age=86400'
        return response


class FormulaLookupView(View):
    """Full text of a handful of formulas, for the hover cards on the analysis page.

    The artifacts a run writes carry only an incipit, and the report tables carry
    only a CO number — neither tells a reader which prayer they are looking at. This
    resolves a batch of references into full text, translations and traditions, in
    two queries whatever the batch size, so the page can fill a hover card without
    holding up anything else it is loading.

    Lookup is by `uuid` for anything a recent run wrote, and by `co` for artifacts
    written before the uuids were carried through. CO numbers are not unique in this
    data — the same number is recorded against genuinely different texts — so a `co`
    lookup can legitimately return several formulas and the caller must show them all.
    """

    #: Enough for any single hover burst; a scraper gains nothing by batching wider.
    MAX_KEYS = 80
    #: Formula text is public (so is /api/formulas_index/), and a run's artifacts are
    #: immutable, so the browser may hold these cards for a while.
    CACHE_SECONDS = 300

    @staticmethod
    def _keys(raw):
        if not raw:
            return []
        seen = []
        for part in raw.split(','):
            part = part.strip()
            if part and part not in seen:
                seen.append(part)
        return seen

    def get(self, request, *args, **kwargs):
        uuids = []
        for key in self._keys(request.GET.get('uuid'))[:self.MAX_KEYS]:
            try:
                uuids.append(str(uuid_module.UUID(key)))
            except (ValueError, AttributeError, TypeError):
                continue
        co_nos = self._keys(request.GET.get('co'))[:self.MAX_KEYS]

        if not uuids and not co_nos:
            return JsonResponse({'formulas': []})

        query = Q()
        if uuids:
            query |= Q(uuid__in=uuids)
        if co_nos:
            query |= Q(co_no__in=co_nos)

        # A CO number shared by dozens of texts would otherwise drag a good part of
        # the catalogue into one hover card.
        matches = Formulas.objects.filter(query).prefetch_related('tradition')
        records = list(matches[:self.MAX_KEYS * 4])

        usage = {
            str(row['formula_uuid']): row
            for row in Content.objects
            .filter(formula_uuid__in=[f.uuid for f in records if f.uuid])
            .values('formula_uuid')
            .annotate(
                occurrences=Count('id'),
                manuscripts=Count('manuscript_uuid', distinct=True),
            )
        }

        payload = []
        for formula in records:
            key = str(formula.uuid) if formula.uuid else None
            counts = usage.get(key, {})
            payload.append({
                'uuid': key,
                'id': formula.id,
                'co_no': formula.co_no or '',
                'text': formula.text or '',
                'translation_en': formula.translation_en or '',
                'translation_pl': formula.translation_pl or '',
                'traditions': [
                    {'name': tradition.name, 'color_rgb': tradition.color_rgb}
                    for tradition in formula.tradition.all()
                ],
                'occurrences': counts.get('occurrences', 0),
                'manuscripts': counts.get('manuscripts', 0),
            })

        response = JsonResponse({'formulas': payload})
        response['Cache-Control'] = f'public, max-age={self.CACHE_SECONDS}'
        return response
