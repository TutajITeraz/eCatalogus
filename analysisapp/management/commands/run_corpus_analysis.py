"""Run the corpus analysis pipeline from the command line.

The same entry point Celery uses, so a run can be reproduced or debugged without a
broker. Useful during data work: `--dry-run` reports what the corpus looks like
without computing or writing anything.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from analysisapp import pipeline
from analysisapp.extract import build_cohorts, load_corpus
from analysisapp.models import AnalysisRun


class Command(BaseCommand):
    help = 'Compare every indexed manuscript by prayer content, order and rubric.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-items', type=int, default=pipeline.DEFAULT_PARAMS['min_items'],
            help='Skip manuscripts with fewer formula-linked content rows than this.',
        )
        parser.add_argument(
            '--min-manuscripts', type=int, default=pipeline.DEFAULT_PARAMS['min_manuscripts'],
            help='Skip cohorts smaller than this.',
        )
        parser.add_argument(
            '--manuscripts', type=str, default=None,
            help='Comma-separated manuscript uuids to restrict the corpus to.',
        )
        parser.add_argument(
            '--min-block-support', type=int,
            default=pipeline.DEFAULT_PARAMS['min_block_support'],
            help='Witnesses a run of prayers needs before it counts as a shared block.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report the corpus and cohorts, then stop without computing.',
        )

    def handle(self, *args, **options):
        manuscript_uuids = None
        if options['manuscripts']:
            manuscript_uuids = [u.strip() for u in options['manuscripts'].split(',') if u.strip()]

        if options['dry_run']:
            return self._dry_run(options, manuscript_uuids)

        run = AnalysisRun.objects.create(params={
            'min_items': options['min_items'],
            'min_manuscripts': options['min_manuscripts'],
            'min_block_support': options['min_block_support'],
            'manuscript_uuids': manuscript_uuids,
        })
        self.stdout.write(f'Run {run.uuid} started.')

        def report(percent, stage):
            self.stdout.write(f'  [{percent:3d}%] {stage}')

        try:
            manifest = pipeline.execute_run(run, callback=report)
        except Exception as exc:
            raise CommandError(f'Run {run.uuid} failed: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Run {run.uuid} finished.'))
        self.stdout.write(f'Artifacts: {run.storage_dir}')
        for cohort in manifest['cohorts']:
            self.stdout.write(
                f"  {cohort['slug']}: {cohort['manuscripts']} manuscripts, "
                f"{cohort['formulas']} formulas, {cohort['blocks']} blocks, "
                f"layers={cohort['layers']}, suggested_k={cohort['suggested_k']}"
            )
            validation = cohort.get('validation') or {}
            if validation.get('performed'):
                self.stdout.write(
                    f"    held-out ARI {validation['adjusted_rand_index']:.3f} "
                    f"({validation['best_method']}, "
                    f"{validation['n_manuscripts']} witnesses)"
                )
            elif cohort.get('exemplars'):
                self.stdout.write(
                    f"    held-out validation skipped: {validation.get('reason', 'unknown')}"
                )

    def _dry_run(self, options, manuscript_uuids):
        corpus = load_corpus(min_items=options['min_items'], manuscript_uuids=manuscript_uuids)
        cohorts = build_cohorts(corpus, min_manuscripts=options['min_manuscripts'])

        self.stdout.write(json.dumps({
            'manuscripts': corpus.n_manuscripts,
            'formulas': corpus.n_formulas,
            'traditions': [t.name for t in corpus.traditions],
            'rubric_coverage': round(corpus.rubric_coverage, 4),
            'skipped': corpus.skipped_manuscripts,
            'cohorts': [
                {'slug': slug, 'label': label, 'manuscripts': len(indices)}
                for slug, label, indices in cohorts
            ],
        }, indent=2, ensure_ascii=False))
