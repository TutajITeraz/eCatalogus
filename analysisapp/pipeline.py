"""Pipeline orchestration.

Runs both stages over every cohort and writes the artifacts the display layer
reads. Nothing is computed on request: by the time the page loads, every number it
shows already exists in a file.
"""

import traceback
from typing import Callable, List, Optional

import numpy as np
from django.utils import timezone

from . import blocks as blocks_module
from . import formula_space as stage_one
from . import ms_space as stage_two
from . import report as report_module
from . import rubrics as rubrics_module
from .artifacts import ArtifactWriter
from .cohort import build_cohort_view
from .extract import build_cohorts, load_corpus
from .models import PIPELINE_VERSION, AnalysisRun

DEFAULT_PARAMS = {
    'min_items': 20,
    'min_manuscripts': 2,
    'metric': stage_two.PRIMARY_METRIC,
    'min_cluster_size': 5,
    'min_block_support': blocks_module.MIN_SUPPORT,
    'manuscript_uuids': None,
}

ProgressCallback = Callable[[int, str], None]


class Progress:
    """Writes progress back to the run row so the UI can poll it."""

    def __init__(self, run: AnalysisRun, callback: Optional[ProgressCallback] = None):
        self.run = run
        self.callback = callback
        self._last = -1

    def set(self, percent: float, stage: str):
        value = max(0, min(100, int(percent)))
        if value == self._last and stage == self.run.stage:
            return
        self._last = value
        self.run.progress = value
        self.run.stage = stage[:255]
        self.run.save(update_fields=['progress', 'stage'])
        if self.callback:
            self.callback(value, stage)


def execute_run(run: AnalysisRun, callback: Optional[ProgressCallback] = None) -> dict:
    """Run the whole analysis. Raises only after recording the failure on the run."""
    progress = Progress(run, callback)
    params = {**DEFAULT_PARAMS, **(run.params or {})}

    run.status = AnalysisRun.STATUS_RUNNING
    run.started_at = timezone.now()
    run.error = None
    run.pipeline_version = PIPELINE_VERSION
    run.save(update_fields=['status', 'started_at', 'error', 'pipeline_version'])

    writer = ArtifactWriter(run)

    try:
        progress.set(2, 'loading corpus')
        corpus = load_corpus(
            min_items=params['min_items'],
            manuscript_uuids=params['manuscript_uuids'],
        )
        if not corpus.manuscripts:
            raise ValueError(
                'No manuscript has enough content rows with a standardized formula. '
                f'Lower min_items (currently {params["min_items"]}) or index more content.'
            )

        cohorts = build_cohorts(corpus, min_manuscripts=params['min_manuscripts'])
        if not cohorts:
            raise ValueError('No cohort reached the minimum number of manuscripts.')

        manifest = {
            'run_uuid': str(run.uuid),
            'pipeline_version': PIPELINE_VERSION,
            'created_at': run.created_at.isoformat(),
            'params': params,
            'corpus': {
                'manuscripts': corpus.n_manuscripts,
                'formulas': corpus.n_formulas,
                'traditions': [t.name for t in corpus.traditions],
                'rubric_coverage': round(corpus.rubric_coverage, 4),
                'skipped_manuscripts': corpus.skipped_manuscripts,
                'genres_declared': bool(corpus.genre_titles),
            },
            'cohorts': [],
        }

        span = 92.0 / len(cohorts)
        for position, (slug, label, indices) in enumerate(cohorts):
            base = 4.0 + position * span

            def cohort_progress(fraction: float, message: str, base=base, label=label):
                progress.set(base + fraction * span * 0.8, f'{label}: {message}')

            progress.set(base, f'{label}: preparing')
            summary = _process_cohort(
                writer, corpus, slug, label, indices, params, cohort_progress,
            )
            manifest['cohorts'].append(summary)

        progress.set(98, 'writing manifest')
        writer.write_json('_run', 'manifest', manifest, cohort_label='Run')

        run.summary = {
            'manuscripts': corpus.n_manuscripts,
            'formulas': corpus.n_formulas,
            'cohorts': [
                {'slug': c['slug'], 'label': c['label'], 'manuscripts': c['manuscripts']}
                for c in manifest['cohorts']
            ],
        }
        run.status = AnalysisRun.STATUS_DONE
        run.finished_at = timezone.now()
        run.progress = 100
        run.stage = 'done'
        run.save(update_fields=['status', 'finished_at', 'progress', 'stage', 'summary'])
        return manifest

    except Exception as exc:
        run.status = AnalysisRun.STATUS_FAILED
        run.finished_at = timezone.now()
        run.error = f'{exc}\n\n{traceback.format_exc()}'
        run.stage = 'failed'
        run.save(update_fields=['status', 'finished_at', 'error', 'stage'])
        raise


def _process_cohort(writer, corpus, slug, label, indices, params, progress) -> dict:
    view = build_cohort_view(corpus, slug, label, indices)

    progress(0.05, 'stage I — formula space')
    formula_space = stage_one.analyse(view, min_cluster_size=params['min_cluster_size'])
    exemplars = stage_one.detect_exemplars(view)

    progress(0.35, 'validating against held-out witnesses')
    validation = _holdout_validation(corpus, view, exemplars, params)

    progress(0.45, 'stage II — manuscript space')
    manuscript_space = stage_two.analyse(
        view, formula_space,
        progress=lambda fraction, message: progress(0.45 + 0.3 * fraction, message),
    )

    progress(0.78, 'finding shared blocks')
    block_list = blocks_module.find_blocks(view, min_support=params['min_block_support'])

    progress(0.85, 'rubric stability')
    rubric_analysis = rubrics_module.analyse(view)

    progress(0.9, 'writing artifacts')
    _write_stage_one(writer, view, formula_space, exemplars, slug, label)
    _write_stage_two(writer, view, formula_space, manuscript_space, slug, label)
    writer.write_json(slug, 'blocks', {'blocks': block_list}, cohort_label=label)
    writer.write_json(slug, 'rubrics', rubric_analysis, cohort_label=label)

    progress(0.97, 'building report')
    document = report_module.build(
        view, formula_space, manuscript_space, block_list, rubric_analysis,
        exemplars, validation, params,
    )
    writer.write_json(slug, 'report', document, cohort_label=label)

    return {
        'slug': slug,
        'label': label,
        'manuscripts': view.n_manuscripts,
        'formulas': view.n_formulas,
        'layers': formula_space.layers['k'] if formula_space.layers else None,
        'suggested_k': manuscript_space.suggested_k,
        'blocks': len(block_list),
        'exemplars': exemplars,
        'validation': validation,
        'rubric_coverage': rubric_analysis.get('coverage', 0.0),
        'artifacts': sorted(
            writer.run.artifacts.filter(cohort=slug).values_list('kind', flat=True)
        ),
    }


def _holdout_validation(corpus, view, exemplars, params) -> dict:
    """Re-derive the traditions without the witnesses that define them.

    If a manuscript contains essentially all of a tradition's formulas, then
    recovering that tradition from co-occurrence is close to tautology. Removing
    those witnesses and asking whether the remaining books still reproduce the
    traditions is the honest version of the question.
    """
    if not exemplars:
        return {'performed': False, 'reason': 'no exemplar witnesses detected'}

    excluded = {e['manuscript_index'] for e in exemplars}
    remaining = [ms.index for ms in view.manuscripts if ms.index not in excluded]
    if len(remaining) < 3:
        return {
            'performed': False,
            'excluded_manuscripts': len(excluded),
            'reason': f'only {len(remaining)} witnesses would remain',
        }

    sub_view = build_cohort_view(corpus, f'{view.slug}-heldout', f'{view.label} (held out)', remaining)
    known = stage_one.tradition_labels(sub_view)
    if len({int(label) for label in known if label >= 0}) < 2:
        return {
            'performed': False,
            'excluded_manuscripts': len(excluded),
            'reason': 'fewer than two traditions remain among the held-out formulas',
        }

    space = stage_one.build_features(sub_view)
    space = stage_one.cluster_formulas(space, sub_view, min_cluster_size=params['min_cluster_size'])
    space = stage_one.fit_layers(sub_view, space)
    space = stage_one.score_against_traditions(space, sub_view)

    scored = {
        method: result for method, result in space.agreement.items()
        if 'adjusted_rand_index' in result
    }
    if not scored:
        return {
            'performed': False,
            'excluded_manuscripts': len(excluded),
            'reason': 'no clustering could be scored on the held-out cohort',
        }

    best_method = max(scored, key=lambda m: scored[m]['adjusted_rand_index'])
    best = scored[best_method]
    return {
        'performed': True,
        'excluded_manuscripts': sorted(excluded),
        'n_manuscripts': sub_view.n_manuscripts,
        'n_formulas': sub_view.n_formulas,
        'best_method': best_method,
        'adjusted_rand_index': best['adjusted_rand_index'],
        'normalized_mutual_info': best['normalized_mutual_info'],
        'comparable_formulas': best['comparable_formulas'],
        'all_methods': {
            method: {
                'adjusted_rand_index': result['adjusted_rand_index'],
                'normalized_mutual_info': result['normalized_mutual_info'],
            }
            for method, result in scored.items()
        },
    }


def _write_stage_one(writer, view, space, exemplars, slug, label):
    layers = space.layers
    layer_weights = layers['formula_weights'] if layers else None

    nodes = []
    for local in range(view.n_formulas):
        meta = view.formula_meta(local)
        node = {
            'i': local,
            'uuid': meta.uuid,
            'co_no': meta.co_no,
            'incipit': meta.incipit,
            'df': int(space.df[local]),
            'idf': round(float(space.idf[local]), 4),
            'count': int(space.total_counts[local]),
            'position': round(float(space.mean_position[local]), 4),
            'spread': round(float(space.position_spread[local]), 4),
            'traditions': [view.corpus.traditions[t].name for t in meta.tradition_indices],
        }
        for method, labels in space.labels.items():
            node[method] = int(labels[local])
        if layer_weights is not None:
            column = layer_weights[:, local]
            total = float(column.sum())
            node['layer'] = int(column.argmax())
            node['layer_strength'] = round(float(column.max() / total), 4) if total else 0.0
        nodes.append(node)

    writer.write_json(slug, 'formulas', {
        'cohort': slug,
        'cohort_label': label,
        'manuscripts': [
            {'uuid': ms.uuid, 'label': ms.label} for ms in view.manuscripts
        ],
        'traditions': [
            {'name': t.name, 'uuid': t.uuid, 'color_rgb': t.color_rgb}
            for t in view.corpus.traditions
        ],
        'formulas': nodes,
    }, cohort_label=label)

    writer.write_json(slug, 'formula_clusters', {
        'methods': {
            method: {
                'labels': [int(x) for x in labels],
                'n_clusters': len({int(x) for x in labels if x >= 0}),
                'n_outliers': int((labels < 0).sum()),
                'agreement': space.agreement.get(method, {}),
            }
            for method, labels in space.labels.items()
        },
        'exemplar_witnesses': exemplars,
        'notes': space.notes,
    }, cohort_label=label)

    if layers:
        H = layers['formula_weights']
        W = layers['manuscript_weights']
        shares = stage_two.normalize_rows(W)
        distinctiveness = H / np.maximum(H.sum(axis=0), 1e-12)

        layer_payload = []
        for index in range(layers['k']):
            score = H[index] * distinctiveness[index]
            top = np.argsort(score)[::-1][:60]
            layer_payload.append({
                'index': index,
                'top_formulas': [
                    {
                        'uuid': view.formula_meta(int(f)).uuid,
                        'co_no': view.formula_meta(int(f)).co_no,
                        'incipit': view.formula_meta(int(f)).incipit,
                        'weight': round(float(H[index, f]), 4),
                        'distinctiveness': round(float(distinctiveness[index, f]), 4),
                        'traditions': [
                            view.corpus.traditions[t].name
                            for t in view.formula_meta(int(f)).tradition_indices
                        ],
                    }
                    for f in top
                ],
            })

        writer.write_json(slug, 'layers', {
            'k': layers['k'],
            'candidates': layers['candidates'],
            'layers': layer_payload,
            'manuscript_shares': [
                {
                    'uuid': view.manuscripts[i].uuid,
                    'label': view.manuscripts[i].label,
                    'shares': [round(float(v), 4) for v in shares[i]],
                }
                for i in range(view.n_manuscripts)
            ],
        }, cohort_label=label)

    writer.write_json(slug, 'formula_embedding', {
        'cohort': slug,
        'dimensions': {
            key: [[round(float(v), 4) for v in row] for row in coordinates]
            for key, coordinates in space.embedding.items()
        },
        'note': 'Projection for inspection only; distances are not metric.',
    }, cohort_label=label)

    writer.write_json(slug, 'attribution_proposals', {
        'proposals': stage_one.propose_attributions(space, view),
        'method': 'agglomerative',
        'min_known_members': stage_one.MIN_KNOWN_FOR_ATTRIBUTION,
        'min_modal_share': stage_one.MIN_MODAL_SHARE_FOR_ATTRIBUTION,
        'exemplar_warning': bool(exemplars),
    }, cohort_label=label)


def _write_stage_two(writer, view, formula_space, space, slug, label):
    n = view.n_manuscripts

    writer.write_json(slug, 'manuscripts', {
        'cohort': slug,
        'cohort_label': label,
        'manuscripts': [
            {
                'i': i,
                'uuid': ms.uuid,
                'label': ms.label,
                'shelf_mark': ms.shelf_mark,
                'common_name': ms.common_name,
                'year_from': ms.year_from,
                'year_to': ms.year_to,
                'century_from': ms.century_from,
                'century_to': ms.century_to,
                'genres': [view.corpus.genre_titles.get(g, g) for g in ms.genre_uuids],
                'n_items': len(view.seqs[i]),
                'n_distinct': len(view.counts[i]),
                'rubric_coverage': round(ms.rubric_coverage, 4),
                'unordered_items': ms.unordered_items,
                'tradition_profile': (
                    [round(float(v), 4) for v in space.tradition_profiles[i]]
                    if space.tradition_profiles is not None else []
                ),
                'layer_profile': (
                    [round(float(v), 4) for v in space.layer_profiles[i]]
                    if space.layer_profiles is not None else []
                ),
            }
            for i, ms in enumerate(view.manuscripts)
        ],
        'tradition_columns': [t.name for t in view.corpus.traditions] + ['Unattributed'],
    }, cohort_label=label)

    # One file with every metric: the page switches between them without refetching.
    def condensed(matrix):
        return [round(float(matrix[i, j]), 5)
                for i in range(n) for j in range(i + 1, n)]

    matrices = {name: condensed(matrix) for name, matrix in space.matrices.items()}
    matrices['mean_displacement'] = condensed(space.displacement)
    matrices['rubric_agreement'] = condensed(space.rubric_agreement)

    writer.write_json(slug, 'matrices', {
        'n': n,
        'layout': 'condensed upper triangle, row-major, excluding the diagonal',
        'primary': stage_two.PRIMARY_METRIC,
        'higher_is_closer': {
            name: name != 'mean_displacement' for name in matrices
        },
        'metrics': matrices,
    }, cohort_label=label)

    writer.write_json(slug, 'ms_clusters', {
        'leaf_order': space.leaf_order,
        'linkage': space.linkage.tolist() if space.linkage is not None else [],
        'newick': stage_two.to_newick(space.linkage, [ms.label for ms in view.manuscripts]),
        'cuts': {str(k): labels for k, labels in space.cuts.items()},
        'silhouette': {str(k): round(v, 4) for k, v in space.silhouette.items()},
        'suggested_k': space.suggested_k,
        'agreement': space.agreement,
        'notes': space.notes,
    }, cohort_label=label)

    writer.write_json(slug, 'ms_embedding', {
        'coordinates': (
            [[round(float(v), 4) for v in row] for row in space.embedding_2d]
            if space.embedding_2d is not None else []
        ),
        'explained': space.embedding_stress,
        'method': 'classical MDS (principal coordinates) on 1 - idf_cosine',
    }, cohort_label=label)

    writer.write_json(slug, 'pairs_top', stage_two.top_pairs(view, space), cohort_label=label)

    writer.write_json(slug, 'presence', _presence_payload(view, formula_space, space),
                      cohort_label=label)

    if space.linkage is not None:
        similarity = space.matrices[stage_two.PRIMARY_METRIC]
        distance = np.clip(1.0 - similarity, 0.0, None)
        np.fill_diagonal(distance, 0.0)
        writer.write_text(
            slug, 'nexus', 'distances.nex',
            stage_two.to_nexus(distance, [ms.label for ms in view.manuscripts]),
            cohort_label=label,
            meta={'purpose': 'open in SplitsTree to compute a NeighborNet split network'},
        )
        writer.write_text(
            slug, 'newick', 'dendrogram.nwk',
            stage_two.to_newick(space.linkage, [ms.label for ms in view.manuscripts]),
            cohort_label=label,
        )


def _presence_payload(view, formula_space, space) -> dict:
    """Formula x manuscript presence, seriated, stored sparsely."""
    leaf_order = space.leaf_order or list(range(view.n_manuscripts))
    rank = {ms_index: position for position, ms_index in enumerate(leaf_order)}

    rows = []
    for local in range(view.n_formulas):
        witnesses = sorted(
            (rank[i] for i in range(view.n_manuscripts) if local in view.counts[i])
        )
        if witnesses:
            rows.append((local, witnesses))

    # Classic seriation for presence/absence data: sort by the pattern itself, so
    # formulas shared by the same witnesses end up adjacent and block structure
    # becomes visible without any further processing.
    rows.sort(key=lambda item: (
        item[1][0], tuple(item[1]), float(formula_space.mean_position[item[0]]),
    ))

    return {
        'manuscript_order': leaf_order,
        'manuscript_labels': [view.manuscripts[i].label for i in leaf_order],
        'formula_order': [local for local, _ in rows],
        'rows': [witnesses for _, witnesses in rows],
        'note': 'Column indices refer to positions in manuscript_order, not to manuscript indices.',
    }
