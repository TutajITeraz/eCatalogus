from celery import shared_task

from .models import AnalysisRun
from .pipeline import execute_run


@shared_task(bind=True)
def run_corpus_analysis_task(self, run_uuid):
    """Background entry point for the corpus analysis pipeline.

    Deliberately without retries: a run takes minutes and writes artifacts as it
    goes, so silently starting again would duplicate work and hide the cause. The
    failure is recorded on the run row, where the UI can show it.
    """
    run = AnalysisRun.objects.get(uuid=run_uuid)
    run.celery_task_id = self.request.id
    run.save(update_fields=['celery_task_id'])

    manifest = execute_run(run)
    return {
        'status': 'success',
        'run_uuid': str(run.uuid),
        'cohorts': [
            {'slug': c['slug'], 'manuscripts': c['manuscripts'], 'formulas': c['formulas']}
            for c in manifest['cohorts']
        ],
    }
