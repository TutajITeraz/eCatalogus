"""Stage I — the space of prayers.

This is the primary stage. Traditions in this database hang on formulas, not on
manuscripts, so the clusters we are looking for are clusters *of prayers*: groups
that travel together through the corpus, sit in the same part of the book and keep
the same neighbours. Manuscript families (Stage II) follow from this, not the other
way round.

A formula is described by four things:

1. which manuscripts carry it, and how often — the co-occurrence pattern;
2. where in the book it sits — mean normalized position and how much that varies;
3. what stands next to it — a bag of neighbouring formulas;
4. which rubric it falls under, when the data has one.

Three complementary clusterings are produced from that description, because they
answer different questions: HDBSCAN gives hard groups and names outliers, NMF gives
soft *layers* (a manuscript is a mixture of them, which is how a liturgist would
say "Gregorian with a Gelasian supplement"), and agglomerative clustering gives an
interpretable hierarchy.
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy import sparse
from sklearn.cluster import AgglomerativeClustering, HDBSCAN
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.manifold import TSNE
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.preprocessing import normalize

from .cohort import CohortView

#: Occurrences on each side counted as "neighbours" when building context vectors.
CONTEXT_WINDOW = 3
#: Dimensions kept from the neighbour bag. The raw context space has one dimension
#: per formula, which is far too wide and far too sparse to cluster directly.
CONTEXT_COMPONENTS = 64

#: Relative weight of each block in the combined feature vector. Co-occurrence is
#: the strongest evidence of a shared tradition; position and context refine it.
BLOCK_WEIGHTS = {'incidence': 1.0, 'context': 0.5, 'positional': 0.3}

#: A cluster must contain at least this many formulas of known tradition before it
#: is allowed to suggest an attribution for its unattributed members.
MIN_KNOWN_FOR_ATTRIBUTION = 5
#: And that tradition must account for at least this share of the known members.
MIN_MODAL_SHARE_FOR_ATTRIBUTION = 0.8

RANDOM_STATE = 0


@dataclass
class FormulaSpace:
    """Everything Stage I computes for one cohort."""

    features: np.ndarray                       # F x D combined descriptor
    df: np.ndarray                             # F, document frequency
    idf: np.ndarray                            # F
    total_counts: np.ndarray                   # F, occurrences across the cohort
    mean_position: np.ndarray                  # F
    position_spread: np.ndarray                # F, std of position across occurrences
    labels: Dict[str, np.ndarray] = field(default_factory=dict)      # method -> F
    layers: Optional[dict] = None                                    # NMF result
    embedding: Dict[str, np.ndarray] = field(default_factory=dict)   # '2d' / '3d'
    agreement: Dict[str, dict] = field(default_factory=dict)         # method -> scores
    notes: List[str] = field(default_factory=list)


def build_features(view: CohortView,
                   window: int = CONTEXT_WINDOW,
                   context_components: int = CONTEXT_COMPONENTS):
    """Assemble the formula descriptor matrix and the per-formula statistics."""
    n_formulas = view.n_formulas
    n_manuscripts = view.n_manuscripts

    counts = view.incidence_matrix().T                 # F x N
    idf = view.idf()
    df = view.document_frequency()
    total_counts = counts.sum(axis=1)

    # 1. Co-occurrence pattern. Manuscripts are weighted by idf-free presence, but
    # each formula row is L2-normalized so that a formula occurring many times does
    # not merely look "bigger" than a rare one — what matters is the shape.
    incidence = normalize(np.log1p(counts), norm='l2', axis=1)

    # 2. Position: where in the book, and how stable that is.
    mean_position, position_spread = _position_statistics(view)
    positional = np.column_stack([
        mean_position,
        position_spread,
        np.log1p(total_counts) / max(math.log1p(total_counts.max()), 1e-9),
    ])

    # 3. Context: what stands next to it.
    context = _context_matrix(view, window)
    if context.nnz and n_formulas > 2:
        components = int(min(context_components, n_formulas - 1, context.shape[1] - 1))
        if components >= 2:
            svd = TruncatedSVD(n_components=components, random_state=RANDOM_STATE)
            context_dense = normalize(svd.fit_transform(context), norm='l2', axis=1)
        else:
            context_dense = np.zeros((n_formulas, 1))
    else:
        context_dense = np.zeros((n_formulas, 1))

    features = np.hstack([
        incidence * BLOCK_WEIGHTS['incidence'],
        context_dense * BLOCK_WEIGHTS['context'],
        positional * BLOCK_WEIGHTS['positional'],
    ])

    return FormulaSpace(
        features=features,
        df=df,
        idf=idf,
        total_counts=total_counts.astype(np.int64),
        mean_position=mean_position,
        position_spread=position_spread,
        notes=[] if n_manuscripts >= 4 else [
            f'Only {n_manuscripts} manuscripts in this cohort: co-occurrence patterns '
            f'can take at most {2 ** n_manuscripts} distinct shapes, so formula '
            f'clusters are coarse and should be read as provisional.'
        ],
    )


def _position_statistics(view: CohortView):
    """Mean and spread of each formula's normalized position across the cohort."""
    sums = np.zeros(view.n_formulas)
    squares = np.zeros(view.n_formulas)
    counts = np.zeros(view.n_formulas)

    for seq, positions in zip(view.seqs, view.positions):
        for local, position in zip(seq, positions):
            sums[local] += position
            squares[local] += position * position
            counts[local] += 1

    safe = np.maximum(counts, 1.0)
    mean = sums / safe
    variance = np.maximum(squares / safe - mean * mean, 0.0)
    return mean, np.sqrt(variance)


def _context_matrix(view: CohortView, window: int) -> sparse.csr_matrix:
    """Sparse formula x formula counts of neighbours within `window` occurrences."""
    rows, cols, values = [], [], []
    for seq in view.seqs:
        length = len(seq)
        for i, symbol in enumerate(seq):
            low = max(0, i - window)
            high = min(length, i + window + 1)
            for j in range(low, high):
                if j == i:
                    continue
                rows.append(symbol)
                cols.append(seq[j])
                values.append(1.0)

    if not rows:
        return sparse.csr_matrix((view.n_formulas, view.n_formulas))

    matrix = sparse.coo_matrix(
        (values, (rows, cols)), shape=(view.n_formulas, view.n_formulas),
    ).tocsr()
    matrix.sum_duplicates()
    return matrix


def cluster_formulas(space: FormulaSpace, view: CohortView,
                     min_cluster_size: int = 5,
                     n_clusters: Optional[int] = None) -> FormulaSpace:
    """Hard clusterings: HDBSCAN (with outliers) and agglomerative (hierarchy)."""
    n_formulas = view.n_formulas
    if n_formulas < 4:
        space.labels['hdbscan'] = np.full(n_formulas, -1)
        space.labels['agglomerative'] = np.zeros(n_formulas, dtype=int)
        space.notes.append('Too few formulas to cluster meaningfully.')
        return space

    hdbscan = HDBSCAN(
        min_cluster_size=max(2, min(min_cluster_size, n_formulas // 2)),
        metric='euclidean',
        copy=True,
    )
    space.labels['hdbscan'] = hdbscan.fit_predict(space.features)

    if n_clusters is None:
        # Aim for clusters of roughly the same granularity as HDBSCAN found, but
        # keep the count in a range a human can actually read.
        found = len({label for label in space.labels['hdbscan'] if label >= 0})
        n_clusters = int(min(max(found or 5, 3), 40, n_formulas - 1))

    agglomerative = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
    space.labels['agglomerative'] = agglomerative.fit_predict(space.features)

    # A second cut at the granularity of the known traditions. Comparing a
    # 40-cluster partition against 5 traditions makes the Rand index look terrible
    # even when every cluster is internally pure, so the fair comparison needs a
    # partition of the same coarseness.
    n_traditions = len({label for label in tradition_labels(view) if label >= 0})
    if 2 <= n_traditions < n_formulas:
        matched = AgglomerativeClustering(n_clusters=n_traditions, linkage='ward')
        space.labels['agglomerative_matched'] = matched.fit_predict(space.features)

    return space


def fit_layers(view: CohortView, space: FormulaSpace,
               candidate_ks: Optional[List[int]] = None) -> FormulaSpace:
    """Soft repertoire layers by non-negative matrix factorization.

    W (manuscripts x layers) says how much of each layer a manuscript draws on;
    H (layers x formulas) says which prayers define the layer. Unlike hard
    clustering this admits that a book can be Gregorian *and* carry a Gelasian
    supplement, which is how the sources actually behave.
    """
    matrix = view.incidence_matrix()                # N x F, non-negative counts
    n_manuscripts, n_formulas = matrix.shape
    if n_manuscripts < 3 or n_formulas < 3:
        space.notes.append('Cohort too small for layer analysis.')
        return space

    max_k = int(min(n_manuscripts - 1, 12))
    if max_k < 2:
        space.notes.append('Cohort too small for layer analysis.')
        return space

    if candidate_ks is None:
        candidate_ks = list(range(2, max_k + 1))
    candidate_ks = [k for k in candidate_ks if 2 <= k <= max_k]
    if not candidate_ks:
        return space

    weighted = matrix * space.idf[np.newaxis, :]
    trials = []
    for k in candidate_ks:
        model = NMF(
            n_components=k, init='nndsvda', random_state=RANDOM_STATE,
            max_iter=800, tol=1e-5,
        )
        W = model.fit_transform(weighted)
        H = model.components_
        trials.append({'k': k, 'error': float(model.reconstruction_err_), 'W': W, 'H': H})

    best = _select_k_by_elbow(trials)

    space.layers = {
        'k': best['k'],
        'candidates': [{'k': t['k'], 'reconstruction_error': t['error']} for t in trials],
        'manuscript_weights': best['W'],
        'formula_weights': best['H'],
    }
    # The layer a formula weighs most in, so the soft factorization can be scored
    # against the known traditions on the same footing as the hard clusterings.
    space.labels['nmf_layer'] = np.asarray(best['H'].argmax(axis=0), dtype=int)
    return space


def _select_k_by_elbow(trials):
    """Pick the k after which extra layers stop buying much reconstruction."""
    if len(trials) == 1:
        return trials[0]
    errors = [t['error'] for t in trials]
    first, last = errors[0], errors[-1]
    span = first - last
    if span <= 1e-12:
        return trials[0]
    # Largest distance from the straight line between the first and last point.
    best_index, best_distance = 0, -1.0
    for i, error in enumerate(errors):
        expected = first - span * (i / (len(errors) - 1))
        distance = expected - error
        if distance > best_distance:
            best_index, best_distance = i, distance
    return trials[best_index]


def embed_formulas(space: FormulaSpace, view: CohortView,
                   method: str = 'tsne') -> FormulaSpace:
    """2D and 3D coordinates for the interactive maps."""
    n_formulas = view.n_formulas
    if n_formulas < 4:
        space.embedding['2d'] = np.zeros((n_formulas, 2))
        space.embedding['3d'] = np.zeros((n_formulas, 3))
        return space

    features = space.features
    if method == 'tsne' and n_formulas >= 10:
        perplexity = float(min(30, max(5, (n_formulas - 1) / 3)))
        for dimensions in (2, 3):
            model = TSNE(
                n_components=dimensions, perplexity=perplexity,
                init='pca', random_state=RANDOM_STATE, max_iter=1000,
            )
            space.embedding[f'{dimensions}d'] = model.fit_transform(features)
    else:
        for dimensions in (2, 3):
            components = min(dimensions, features.shape[1])
            svd = TruncatedSVD(n_components=components, random_state=RANDOM_STATE)
            coordinates = svd.fit_transform(features)
            if coordinates.shape[1] < dimensions:
                pad = np.zeros((n_formulas, dimensions - coordinates.shape[1]))
                coordinates = np.hstack([coordinates, pad])
            space.embedding[f'{dimensions}d'] = coordinates

    # Scale to a comfortable range for the three.js scene.
    for key, coordinates in space.embedding.items():
        extent = np.abs(coordinates).max() or 1.0
        space.embedding[key] = coordinates / extent * 20.0

    return space


def tradition_labels(view: CohortView) -> np.ndarray:
    """Single tradition label per formula, or -1.

    Formulas carrying several traditions are left unlabelled for scoring purposes:
    a multi-tradition formula has no single right answer, and including it would
    make the agreement scores unreadable. They are counted separately in the report.
    """
    labels = np.full(view.n_formulas, -1, dtype=int)
    for local, global_index in enumerate(view.formula_ids):
        traditions = view.corpus.formulas[global_index].tradition_indices
        if len(traditions) == 1:
            labels[local] = traditions[0]
    return labels


#: A witness covering at least this share of a tradition's formulas is almost
#: certainly the reference edition that tradition was defined from.
EXEMPLAR_COVERAGE = 0.95


def detect_exemplars(view: CohortView) -> List[dict]:
    """Find witnesses that *define* a tradition rather than merely belong to it.

    If a manuscript contains essentially every formula attributed to some tradition,
    then that attribution was almost certainly read off this very book. Any
    clustering that then "recovers" the tradition from co-occurrence has largely
    rediscovered its own input, and the agreement score is circular.

    Detecting this is not a nicety: without it the pipeline reports a near-perfect
    result that means much less than it appears to.
    """
    known = tradition_labels(view)
    exemplars = []

    for tradition in view.corpus.traditions:
        members = np.where(known == tradition.index)[0]
        if len(members) < 5:
            continue
        for i, ms in enumerate(view.manuscripts):
            counts = view.counts[i]
            present = sum(1 for local in members if local in counts)
            coverage = present / len(members)
            if coverage >= EXEMPLAR_COVERAGE:
                exemplars.append({
                    'manuscript_uuid': ms.uuid,
                    'manuscript_label': ms.label,
                    'manuscript_index': ms.index,
                    'tradition': tradition.name,
                    'tradition_uuid': tradition.uuid,
                    'coverage': round(coverage, 4),
                    'tradition_formulas': int(len(members)),
                })

    return exemplars


def score_against_traditions(space: FormulaSpace, view: CohortView) -> FormulaSpace:
    """How well each discovered clustering reproduces the known traditions."""
    known = tradition_labels(view)
    mask = known >= 0
    n_known = int(mask.sum())

    multi = sum(
        1 for global_index in view.formula_ids
        if len(view.corpus.formulas[global_index].tradition_indices) > 1
    )

    for method, labels in space.labels.items():
        if n_known < 2 or len(set(known[mask])) < 2:
            space.agreement[method] = {
                'comparable_formulas': n_known,
                'multi_tradition_formulas': multi,
                'note': 'Not enough formulas with a single known tradition to score.',
            }
            continue

        subset = labels[mask]
        space.agreement[method] = {
            'comparable_formulas': n_known,
            'multi_tradition_formulas': multi,
            'adjusted_rand_index': float(adjusted_rand_score(known[mask], subset)),
            'normalized_mutual_info': float(normalized_mutual_info_score(known[mask], subset)),
            'contingency': _contingency(known[mask], subset, view),
            'per_tradition': _per_tradition_match(known[mask], subset, view),
        }

    return space


def _per_tradition_match(known, discovered, view: CohortView):
    """For each known tradition, the single cluster that best represents it.

    The Rand index collapses to near zero whenever a partition is much finer than
    the reference, which says nothing about whether the clusters are internally
    coherent. Recall and precision against the best-matching cluster answer the
    question a scholar actually asks: is this tradition recognisable as a group?
    """
    by_tradition = defaultdict(Counter)
    cluster_sizes = Counter(int(c) for c in discovered)
    for tradition_index, cluster in zip(known, discovered):
        by_tradition[int(tradition_index)][int(cluster)] += 1

    results = {}
    for tradition_index, counter in sorted(by_tradition.items()):
        real = counter.copy()
        real.pop(-1, None)                     # HDBSCAN noise is not a cluster
        if not real:
            continue
        cluster, hits = real.most_common(1)[0]
        total = sum(counter.values())
        precision = hits / cluster_sizes[cluster] if cluster_sizes[cluster] else 0.0
        recall = hits / total if total else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        results[view.corpus.traditions[tradition_index].name] = {
            'known_formulas': total,
            'best_cluster': cluster,
            'best_cluster_hits': hits,
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
        }
    return results


def _contingency(known, discovered, view: CohortView):
    """Known tradition x discovered cluster counts, as nested plain types."""
    table = defaultdict(Counter)
    for tradition_index, cluster in zip(known, discovered):
        table[int(tradition_index)][int(cluster)] += 1
    return {
        view.corpus.traditions[tradition_index].name: dict(counter)
        for tradition_index, counter in sorted(table.items())
    }


def propose_attributions(space: FormulaSpace, view: CohortView,
                         method: str = 'agglomerative') -> List[dict]:
    """Unattributed formulas that sit firmly inside a single-tradition cluster.

    These are suggestions for a scholar to confirm or reject, not conclusions. The
    confidence reported is simply the tradition's share among that cluster's
    already-attributed members.
    """
    labels = space.labels.get(method)
    if labels is None:
        return []

    known = tradition_labels(view)
    by_cluster = defaultdict(Counter)
    for cluster, tradition_index in zip(labels, known):
        if cluster >= 0 and tradition_index >= 0:
            by_cluster[int(cluster)][int(tradition_index)] += 1

    proposals = []
    for local, cluster in enumerate(labels):
        if cluster < 0:
            continue
        global_index = view.formula_ids[local]
        formula = view.corpus.formulas[global_index]
        if formula.tradition_indices:
            continue

        counter = by_cluster.get(int(cluster))
        if not counter:
            continue
        total_known = sum(counter.values())
        if total_known < MIN_KNOWN_FOR_ATTRIBUTION:
            continue
        tradition_index, hits = counter.most_common(1)[0]
        share = hits / total_known
        if share < MIN_MODAL_SHARE_FOR_ATTRIBUTION:
            continue

        proposals.append({
            'formula_uuid': formula.uuid,
            'co_no': formula.co_no,
            'incipit': formula.incipit,
            'cluster': int(cluster),
            'tradition': view.corpus.traditions[tradition_index].name,
            'tradition_uuid': view.corpus.traditions[tradition_index].uuid,
            'confidence': round(share, 4),
            'cluster_known_members': total_known,
            'document_frequency': int(space.df[local]),
        })

    proposals.sort(key=lambda p: (-p['confidence'], -p['cluster_known_members']))
    return proposals


def analyse(view: CohortView, *, min_cluster_size: int = 5) -> FormulaSpace:
    """Run the whole of Stage I for one cohort."""
    space = build_features(view)
    space = cluster_formulas(space, view, min_cluster_size=min_cluster_size)
    space = fit_layers(view, space)          # also adds the 'nmf_layer' labelling
    space = embed_formulas(space, view)
    space = score_against_traditions(space, view)
    return space
