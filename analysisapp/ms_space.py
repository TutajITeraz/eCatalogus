"""Stage II — the space of manuscripts.

Derived from Stage I, not independent of it. Manuscripts are compared directly on
what they contain and in what order, and additionally placed in the space of
repertoire layers discovered among the prayers.

The all-pairs sweep is the expensive part of the pipeline. Content metrics that can
be written as matrix products are computed in one shot; the order metrics are
inherently sequential and run in a Python loop, which is why `align` had to be
near-linear rather than quadratic.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform
from sklearn.metrics import (
    adjusted_rand_score,
    normalized_mutual_info_score,
    silhouette_score,
)

from .align import align
from .cohort import CohortView
from .metrics import content_metrics, order_metrics, rubric_metrics

#: Similarity matrices produced for every cohort. The UI switches between them.
CONTENT_METRICS = ('jaccard', 'weighted_jaccard', 'containment', 'idf_cosine')
ORDER_METRICS = ('nlcs', 'kendall_tau_b', 'breakpoint_rate', 'bigram_jaccard')

#: The metric clustering and the 2D map are built on unless told otherwise.
PRIMARY_METRIC = 'idf_cosine'

#: How many pairs to describe in full in `pairs_top.json`.
TOP_PAIRS = 40


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """Rows scaled to sum to 1, with all-zero rows left as zeros.

    np.divide(..., where=...) without an explicit `out` leaves the masked entries
    uninitialised — real garbage, not zeros — so every share calculation goes
    through here instead.
    """
    totals = matrix.sum(axis=1, keepdims=True)
    result = np.zeros_like(matrix, dtype=np.float64)
    np.divide(matrix, totals, out=result, where=totals > 0)
    return result

@dataclass
class ManuscriptSpace:
    matrices: Dict[str, np.ndarray] = field(default_factory=dict)
    #: Mean |position difference| and rubric agreement, kept apart from the
    #: similarity matrices because they are not on a 0..1 "more is closer" scale.
    displacement: Optional[np.ndarray] = None
    rubric_agreement: Optional[np.ndarray] = None
    rubric_compared: Optional[np.ndarray] = None

    pair_records: List[dict] = field(default_factory=list)
    linkage: Optional[np.ndarray] = None
    leaf_order: List[int] = field(default_factory=list)
    cuts: Dict[int, List[int]] = field(default_factory=dict)
    silhouette: Dict[int, float] = field(default_factory=dict)
    suggested_k: Optional[int] = None
    embedding_2d: Optional[np.ndarray] = None
    embedding_stress: Optional[float] = None
    tradition_profiles: Optional[np.ndarray] = None
    layer_profiles: Optional[np.ndarray] = None
    agreement: Dict[str, dict] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


def compute_matrices(view: CohortView,
                     progress: Optional[Callable[[float, str], None]] = None
                     ) -> ManuscriptSpace:
    """All pairwise metrics for one cohort."""
    n = view.n_manuscripts
    space = ManuscriptSpace()

    for name in CONTENT_METRICS + ORDER_METRICS:
        matrix = np.zeros((n, n), dtype=np.float64)
        np.fill_diagonal(matrix, 1.0)
        space.matrices[name] = matrix
    space.displacement = np.zeros((n, n))
    space.rubric_agreement = np.zeros((n, n))
    space.rubric_compared = np.zeros((n, n))

    if n < 2:
        space.notes.append('A cohort of fewer than two manuscripts has nothing to compare.')
        return space

    idf = view.idf()
    _fill_vectorized_content(view, space, idf)

    total_pairs = n * (n - 1) // 2
    done = 0
    for i in range(n):
        for j in range(i + 1, n):
            record = _compare_pair(view, i, j, idf)
            for name in ('weighted_jaccard',):
                space.matrices[name][i, j] = space.matrices[name][j, i] = record[name]
            for name in ORDER_METRICS:
                space.matrices[name][i, j] = space.matrices[name][j, i] = record[name]
            space.displacement[i, j] = space.displacement[j, i] = record['mean_displacement']
            space.rubric_agreement[i, j] = space.rubric_agreement[j, i] = record['rubric_agreement']
            space.rubric_compared[i, j] = space.rubric_compared[j, i] = record['rubric_compared']
            space.pair_records.append(record)

            done += 1
            if progress is not None and (done % max(1, total_pairs // 50) == 0):
                progress(done / total_pairs, f'pairwise metrics {done}/{total_pairs}')

    return space


def _fill_vectorized_content(view: CohortView, space: ManuscriptSpace, idf: np.ndarray):
    """Jaccard, containment and idf-cosine as matrix products.

    These three depend only on which formulas are present, so the whole N x N sweep
    reduces to one Gram matrix each — no Python loop needed.
    """
    binary = view.incidence_matrix(binary=True)
    sizes = binary.sum(axis=1)

    intersection = binary @ binary.T
    union = sizes[:, None] + sizes[None, :] - intersection
    with np.errstate(divide='ignore', invalid='ignore'):
        jaccard = np.where(union > 0, intersection / np.maximum(union, 1e-12), 0.0)
        smaller = np.minimum(sizes[:, None], sizes[None, :])
        containment = np.where(smaller > 0, intersection / np.maximum(smaller, 1e-12), 0.0)

        weighted = binary * idf[None, :]
        norms = np.linalg.norm(weighted, axis=1)
        cosine = weighted @ weighted.T
        denominator = norms[:, None] * norms[None, :]
        idf_cosine = np.where(denominator > 0, cosine / np.maximum(denominator, 1e-12), 0.0)

    for name, matrix in (('jaccard', jaccard), ('containment', containment),
                         ('idf_cosine', idf_cosine)):
        np.fill_diagonal(matrix, 1.0)
        space.matrices[name] = np.clip(matrix, 0.0, 1.0)


def _compare_pair(view: CohortView, i: int, j: int, idf: np.ndarray) -> dict:
    seq_a, pos_a, rub_a, counts_a = view.seqs[i], view.positions[i], view.rubrics[i], view.counts[i]
    seq_b, pos_b, rub_b, counts_b = view.seqs[j], view.positions[j], view.rubrics[j], view.counts[j]

    alignment = align(seq_a, pos_a, seq_b, pos_b)
    content = content_metrics(counts_a, counts_b, idf)
    order = order_metrics(alignment, seq_a, pos_a, seq_b, pos_b)
    rubric = rubric_metrics(alignment, rub_a, rub_b)

    size_a, size_b = len(counts_a), len(counts_b)
    return {
        'a': i,
        'b': j,
        'jaccard': content.jaccard,
        'weighted_jaccard': content.weighted_jaccard,
        'containment': content.containment,
        'idf_cosine': content.idf_cosine,
        'shared_formulas': content.shared_formulas,
        'only_a': content.only_a,
        'only_b': content.only_b,
        # Directional coverage: how much of each witness the other accounts for.
        # A large gap is the signature of a fragment inside a complete book.
        'coverage_a': content.shared_formulas / size_a if size_a else 0.0,
        'coverage_b': content.shared_formulas / size_b if size_b else 0.0,
        'nlcs': order.nlcs,
        'kendall_tau_b': order.kendall_tau_b,
        'breakpoint_rate': order.breakpoint_rate,
        'bigram_jaccard': order.bigram_jaccard,
        'mean_displacement': order.mean_displacement,
        'matched_occurrences': order.matched_occurrences,
        'lcs_length': order.lcs_length,
        'shared_occurrences': alignment.shared_occurrences,
        'truncated': alignment.truncated,
        'rubric_agreement': rubric.agreement,
        'rubric_compared': rubric.compared,
        'rubric_coverage': rubric.coverage,
    }


def cluster_manuscripts(view: CohortView, space: ManuscriptSpace,
                        metric: str = PRIMARY_METRIC) -> ManuscriptSpace:
    """Hierarchy, seriation order and candidate cuts."""
    n = view.n_manuscripts
    if n < 3:
        space.leaf_order = list(range(n))
        space.notes.append('Too few manuscripts to build a hierarchy.')
        return space

    similarity = space.matrices[metric]
    distance = np.clip(1.0 - similarity, 0.0, None)
    np.fill_diagonal(distance, 0.0)
    distance = (distance + distance.T) / 2.0
    condensed = squareform(distance, checks=False)

    linkage = hierarchy.linkage(condensed, method='average')
    # Optimal leaf ordering is the seriation: it chooses, among the orderings the
    # dendrogram permits, the one putting similar manuscripts side by side. This is
    # what makes block structure visible in the heatmap.
    linkage = hierarchy.optimal_leaf_ordering(linkage, condensed)
    space.linkage = linkage
    space.leaf_order = [int(i) for i in hierarchy.leaves_list(linkage)]

    for k in range(2, min(n, 12)):
        labels = hierarchy.fcluster(linkage, t=k, criterion='maxclust')
        space.cuts[k] = [int(x) for x in labels]
        if len(set(labels)) > 1:
            try:
                space.silhouette[k] = float(
                    silhouette_score(distance, labels, metric='precomputed')
                )
            except ValueError:
                pass

    if space.silhouette:
        space.suggested_k = max(space.silhouette, key=space.silhouette.get)

    space.embedding_2d, space.embedding_stress = classical_mds(distance)
    return space


def classical_mds(distance: np.ndarray, dimensions: int = 2):
    """Principal coordinates analysis of a distance matrix.

    Closed form: double-centre the squared distances and take the top eigenvectors.
    Deterministic, which matters when the same run has to be reproducible for a
    publication.
    """
    n = distance.shape[0]
    if n < 2:
        return np.zeros((n, dimensions)), 0.0

    squared = distance ** 2
    centering = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * centering @ squared @ centering

    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    keep = min(dimensions, n - 1)
    positive = np.maximum(eigenvalues[:keep], 0.0)
    coordinates = eigenvectors[:, :keep] * np.sqrt(positive)
    if coordinates.shape[1] < dimensions:
        pad = np.zeros((n, dimensions - coordinates.shape[1]))
        coordinates = np.hstack([coordinates, pad])

    total = np.sum(np.maximum(eigenvalues, 0.0))
    explained = float(positive.sum() / total) if total > 0 else 0.0
    return coordinates, explained


def build_profiles(view: CohortView, space: ManuscriptSpace,
                   formula_space=None) -> ManuscriptSpace:
    """Tradition and layer mixtures per manuscript.

    Traditions are attached to formulas, so a manuscript has no tradition label of
    its own — it has a *profile*. Reducing that profile to its strongest component
    is only done for scoring; the report shows the whole mixture.
    """
    n = view.n_manuscripts
    traditions = view.corpus.traditions
    idf = view.idf()

    profiles = np.zeros((n, len(traditions) + 1))     # last column: unattributed
    for i, counts in enumerate(view.counts):
        for local in counts:
            weight = idf[local]
            indices = view.corpus.formulas[view.formula_ids[local]].tradition_indices
            if indices:
                share = weight / len(indices)
                for index in indices:
                    profiles[i, index] += share
            else:
                profiles[i, -1] += weight
    space.tradition_profiles = normalize_rows(profiles)

    if formula_space is not None and formula_space.layers:
        space.layer_profiles = normalize_rows(formula_space.layers['manuscript_weights'])

    return space


def score_clusters(view: CohortView, space: ManuscriptSpace) -> ManuscriptSpace:
    """Agreement between discovered manuscript clusters and tradition profiles."""
    if not space.cuts or space.tradition_profiles is None:
        return space

    # Strongest attributed tradition per manuscript, ignoring the unattributed
    # column; manuscripts whose repertoire is mostly unattributed get no label.
    attributed = space.tradition_profiles[:, :-1]
    if attributed.size == 0 or attributed.shape[1] < 2:
        space.notes.append('Not enough traditions in this cohort to score clusters.')
        return space

    dominant = attributed.argmax(axis=1)
    strength = attributed.max(axis=1)
    mask = strength > 0

    if mask.sum() < 3 or len(set(dominant[mask].tolist())) < 2:
        space.notes.append(
            'Manuscript clusters could not be scored: fewer than two distinct '
            'dominant traditions among the witnesses.'
        )
        return space

    for k, labels in space.cuts.items():
        subset = np.asarray(labels)[mask]
        space.agreement[str(k)] = {
            'adjusted_rand_index': float(adjusted_rand_score(dominant[mask], subset)),
            'normalized_mutual_info': float(normalized_mutual_info_score(dominant[mask], subset)),
            'scored_manuscripts': int(mask.sum()),
        }
    return space


def top_pairs(view: CohortView, space: ManuscriptSpace, limit: int = TOP_PAIRS) -> dict:
    """The pairs worth naming in the report."""
    if not space.pair_records:
        return {'most_similar': [], 'most_distant': [], 'most_asymmetric': [],
                'most_ordered': [], 'least_ordered': []}

    def label(record):
        enriched = dict(record)
        enriched['a_label'] = view.manuscripts[record['a']].label
        enriched['b_label'] = view.manuscripts[record['b']].label
        enriched['a_uuid'] = view.manuscripts[record['a']].uuid
        enriched['b_uuid'] = view.manuscripts[record['b']].uuid
        enriched['asymmetry'] = abs(record['coverage_a'] - record['coverage_b'])
        return enriched

    records = [label(r) for r in space.pair_records]
    ordered = [r for r in records if r['shared_occurrences'] >= 5]

    return {
        'most_similar': sorted(records, key=lambda r: -r['idf_cosine'])[:limit],
        'most_distant': sorted(records, key=lambda r: r['idf_cosine'])[:limit],
        'most_asymmetric': sorted(records, key=lambda r: -r['asymmetry'])[:limit],
        'most_ordered': sorted(ordered, key=lambda r: -r['nlcs'])[:limit],
        'least_ordered': sorted(ordered, key=lambda r: r['nlcs'])[:limit],
    }


def to_newick(linkage: np.ndarray, labels: List[str]) -> str:
    """Dendrogram as Newick, so it can be opened in standard phylogenetic tools.

    Built bottom-up rather than by recursion: a chain-shaped dendrogram over a few
    hundred manuscripts would otherwise be deep enough to hit the recursion limit.
    """
    if linkage is None or len(labels) < 2:
        return ''

    n = len(labels)

    def clean(label: str, index: int) -> str:
        safe = label.translate(str.maketrans({'(': '[', ')': ']', ',': ';', ':': '-'}))
        return safe.strip() or f'taxon_{index}'

    # height[node] is the merge height of that node, 0 for leaves.
    heights = [0.0] * (2 * n - 1)
    rendered = [clean(label, i) for i, label in enumerate(labels)] + [''] * (n - 1)

    for row_index, row in enumerate(linkage):
        node = n + row_index
        left, right, height = int(row[0]), int(row[1]), float(row[2])
        heights[node] = height
        left_branch = max(height - heights[left], 0.0)
        right_branch = max(height - heights[right], 0.0)
        rendered[node] = (
            f'({rendered[left]}:{left_branch:.6f},'
            f'{rendered[right]}:{right_branch:.6f})'
        )

    return rendered[2 * n - 2] + ';'


def to_nexus(distance: np.ndarray, labels: List[str]) -> str:
    """Distance matrix as NEXUS.

    Exported so a researcher can run NeighborNet in SplitsTree: a split network
    shows conflicting signals — contamination, lateral influence — that a single
    tree is forced to hide. Reimplementing that here would cost far more than it
    is worth when the standard tool reads this format directly.
    """
    n = len(labels)
    safe = [
        label.replace(' ', '_').replace("'", '').replace('(', '').replace(')', '')[:60] or f'taxon_{i}'
        for i, label in enumerate(labels)
    ]
    # NEXUS taxon labels must be unique.
    seen = {}
    unique = []
    for name in safe:
        if name in seen:
            seen[name] += 1
            name = f'{name}_{seen[name]}'
        else:
            seen[name] = 0
        unique.append(name)

    lines = [
        '#NEXUS',
        '',
        'BEGIN taxa;',
        f'    DIMENSIONS ntax={n};',
        '    TAXLABELS',
    ]
    lines += [f'        {name}' for name in unique]
    lines += [
        '    ;',
        'END;',
        '',
        'BEGIN distances;',
        f'    DIMENSIONS ntax={n};',
        '    FORMAT triangle=both diagonal labels;',
        '    MATRIX',
    ]
    for i, name in enumerate(unique):
        row = ' '.join(f'{distance[i, j]:.6f}' for j in range(n))
        lines.append(f'        {name} {row}')
    lines += ['    ;', 'END;', '']
    return '\n'.join(lines)


def analyse(view: CohortView, formula_space=None,
            progress: Optional[Callable[[float, str], None]] = None) -> ManuscriptSpace:
    """Run the whole of Stage II for one cohort."""
    space = compute_matrices(view, progress=progress)
    space = cluster_manuscripts(view, space)
    space = build_profiles(view, space, formula_space)
    space = score_clusters(view, space)
    return space
