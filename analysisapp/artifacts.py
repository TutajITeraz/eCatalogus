"""Artifact writing.

Every number the frontend shows is precomputed here and written to a file under
MEDIA_ROOT. The display layer never recomputes anything — it only fetches JSON.
"""

import json
import os
from typing import Optional

import numpy as np
from django.conf import settings

from .models import AnalysisArtifact


class _NumpyEncoder(json.JSONEncoder):
    """numpy scalars and arrays leak in from scipy/sklearn; make them plain JSON."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            value = float(obj)
            return value if np.isfinite(value) else None
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class ArtifactWriter:
    """Writes one run's artifacts and records them in the database."""

    def __init__(self, run):
        self.run = run
        self.root = run.storage_dir
        os.makedirs(self.root, exist_ok=True)

    def write_json(self, cohort: str, kind: str, payload: dict,
                   cohort_label: str = '', meta: Optional[dict] = None) -> AnalysisArtifact:
        cohort_dir = os.path.join(self.root, cohort)
        os.makedirs(cohort_dir, exist_ok=True)

        filename = f'{kind}.json'
        absolute = os.path.join(cohort_dir, filename)
        with open(absolute, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, cls=_NumpyEncoder, ensure_ascii=False, separators=(',', ':'))

        relative = os.path.join(self.run.media_subdir, cohort, filename)
        artifact, _ = AnalysisArtifact.objects.update_or_create(
            run=self.run, cohort=cohort, kind=kind,
            defaults={
                'cohort_label': cohort_label,
                'path': relative,
                'size_bytes': os.path.getsize(absolute),
                'meta': meta or {},
            },
        )
        return artifact

    def write_text(self, cohort: str, kind: str, filename: str, text: str,
                   cohort_label: str = '', meta: Optional[dict] = None) -> AnalysisArtifact:
        """For exports meant to leave the app, such as NEXUS and Newick."""
        cohort_dir = os.path.join(self.root, cohort)
        os.makedirs(cohort_dir, exist_ok=True)

        absolute = os.path.join(cohort_dir, filename)
        with open(absolute, 'w', encoding='utf-8') as fh:
            fh.write(text)

        relative = os.path.join(self.run.media_subdir, cohort, filename)
        artifact, _ = AnalysisArtifact.objects.update_or_create(
            run=self.run, cohort=cohort, kind=kind,
            defaults={
                'cohort_label': cohort_label,
                'path': relative,
                'size_bytes': os.path.getsize(absolute),
                'meta': meta or {},
            },
        )
        return artifact


def media_relative(path: str) -> str:
    """MEDIA_URL-joined path, for building links in the manifest."""
    return f"{settings.MEDIA_URL.rstrip('/')}/{path.replace(os.sep, '/')}"
