import os
import uuid as uuid_lib

from django.conf import settings
from django.db import models


#: Bumped whenever the pipeline output format or metric definitions change, so that
#: an old run can be told apart from a fresh one in the UI.
PIPELINE_VERSION = '1'

#: Everything a run writes lives under MEDIA_ROOT/<ANALYSIS_MEDIA_DIR>/<run uuid>/.
ANALYSIS_MEDIA_DIR = 'analysis'

#: Pseudo-cohort holding every manuscript regardless of liturgical genre.
GLOBAL_COHORT_SLUG = 'all'


class AnalysisRun(models.Model):
    """One execution of the corpus analysis pipeline over one or more cohorts."""

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, db_index=True, editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    pipeline_version = models.CharField(max_length=16, default=PIPELINE_VERSION)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.SET_NULL,
        related_name='analysis_runs', null=True, blank=True,
    )
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)

    #: Input parameters (min_items, cohort selection, metric options, ...).
    params = models.JSONField(default=dict, blank=True)
    #: Small headline numbers, enough to render a run picker without opening artifacts.
    summary = models.JSONField(default=dict, blank=True)

    progress = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=255, blank=True, default='')
    error = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'analysis_run'
        verbose_name = 'Analysis Run'
        verbose_name_plural = 'Analysis Runs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.uuid} ({self.status})'

    @property
    def media_subdir(self):
        """Path of this run's artifact directory, relative to MEDIA_ROOT."""
        return os.path.join(ANALYSIS_MEDIA_DIR, str(self.uuid))

    @property
    def storage_dir(self):
        """Absolute path of this run's artifact directory."""
        return os.path.join(settings.MEDIA_ROOT, self.media_subdir)


class AnalysisArtifact(models.Model):
    """A single JSON (or binary) file produced by a run, for one cohort."""

    run = models.ForeignKey(AnalysisRun, models.CASCADE, related_name='artifacts')
    cohort = models.CharField(max_length=128, db_index=True)
    cohort_label = models.CharField(max_length=255, blank=True, default='')
    kind = models.CharField(max_length=64, db_index=True)
    #: Path relative to MEDIA_ROOT, so artifacts survive a MEDIA_ROOT move.
    path = models.CharField(max_length=512)
    size_bytes = models.BigIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analysis_artifact'
        verbose_name = 'Analysis Artifact'
        verbose_name_plural = 'Analysis Artifacts'
        ordering = ['cohort', 'kind']
        constraints = [
            models.UniqueConstraint(fields=['run', 'cohort', 'kind'], name='analysis_artifact_uniq'),
        ]

    def __str__(self):
        return f'{self.cohort}/{self.kind}'

    @property
    def absolute_path(self):
        return os.path.join(settings.MEDIA_ROOT, self.path)
