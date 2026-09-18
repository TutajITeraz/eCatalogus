"""Pairwise similarity metrics between two manuscripts.

Reference implementations, kept scalar and dependency-free so they can be unit
tested against hand-computed values. `ms_space` recomputes the content metrics in
vectorized form for the full N x N sweep; the order metrics are inherently
sequential and are called from here.
"""

import math
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Sequence

from .align import Alignment, align, count_inversions


@dataclass
class ContentMetrics:
    """How much of the same material two manuscripts carry."""

    #: |A n B| / |A u B| over distinct formulas.
    jaccard: float = 0.0
    #: Multiset version, sensitive to how many times each formula recurs.
    weighted_jaccard: float = 0.0
    #: |A n B| / min(|A|, |B|). A short, fragmentary witness fully contained in a
    #: large one scores 1.0 here while scoring poorly on Jaccard, which is the
    #: difference between "different book" and "same book, less of it indexed".
    containment: float = 0.0
    #: Cosine on idf-weighted incidence. The primary affinity metric: two witnesses
    #: sharing rare orations are far better evidence than two sharing ubiquitous ones.
    idf_cosine: float = 0.0

    shared_formulas: int = 0
    only_a: int = 0
    only_b: int = 0


@dataclass
class OrderMetrics:
    """Whether shared material stands in the same sequence."""

    #: |LCS| / |shared occurrences| — the share of common material in the same
    #: relative order. The most directly interpretable of the four.
    nlcs: float = 0.0
    #: Rank agreement over position-matched occurrences, in [-1, 1].
    kendall_tau_b: float = 0.0
    #: Share of matched neighbours that stay neighbours — liturgical blocks
    #: travelling together.
    breakpoint_rate: float = 0.0
    #: Mean |position difference| over matched occurrences, in [0, 1].
    mean_displacement: float = 0.0
    #: Jaccard over consecutive formula pairs; local order, robust to one large
    #: section having been moved wholesale.
    bigram_jaccard: float = 0.0

    matched_occurrences: int = 0
    lcs_length: int = 0
    truncated: bool = False


@dataclass
class RubricMetrics:
    """Whether shared material sits under the same rubric."""

    agreement: float = 0.0
    compared: int = 0
    #: Share of matched occurrences where both sides carried a standardized rubric.
    coverage: float = 0.0


def content_metrics(counts_a: Dict[int, int], counts_b: Dict[int, int],
                    idf: Optional[Sequence[float]] = None) -> ContentMetrics:
    keys_a, keys_b = set(counts_a), set(counts_b)
    shared = keys_a & keys_b
    union = keys_a | keys_b

    result = ContentMetrics(
        shared_formulas=len(shared),
        only_a=len(keys_a - keys_b),
        only_b=len(keys_b - keys_a),
    )
    if not union:
        return result

    result.jaccard = len(shared) / len(union)

    intersection_weight = sum(min(counts_a[k], counts_b[k]) for k in shared)
    union_weight = sum(max(counts_a.get(k, 0), counts_b.get(k, 0)) for k in union)
    result.weighted_jaccard = intersection_weight / union_weight if union_weight else 0.0

    smaller = min(len(keys_a), len(keys_b))
    result.containment = len(shared) / smaller if smaller else 0.0

    if idf is not None and shared:
        dot = sum(idf[k] * idf[k] for k in shared)
        norm_a = math.sqrt(sum(idf[k] * idf[k] for k in keys_a))
        norm_b = math.sqrt(sum(idf[k] * idf[k] for k in keys_b))
        result.idf_cosine = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    return result


def order_metrics(alignment: Alignment,
                  seq_a: Sequence[int], pos_a: Sequence[float],
                  seq_b: Sequence[int], pos_b: Sequence[float]) -> OrderMetrics:
    result = OrderMetrics(
        lcs_length=len(alignment.lcs_pairs),
        matched_occurrences=len(alignment.positional_pairs),
        truncated=alignment.truncated,
    )

    if alignment.shared_occurrences:
        result.nlcs = len(alignment.lcs_pairs) / alignment.shared_occurrences

    pairs = alignment.positional_pairs
    if len(pairs) >= 2:
        b_order = [j for _i, j in pairs]          # already sorted by A index
        inversions = count_inversions(b_order)
        m = len(pairs)
        total_pairs = m * (m - 1) / 2
        result.kendall_tau_b = 1.0 - 2.0 * inversions / total_pairs

        preserved = sum(
            1 for (i1, j1), (i2, j2) in zip(pairs, pairs[1:])
            if i2 == i1 + 1 and j2 == j1 + 1
        )
        result.breakpoint_rate = preserved / (len(pairs) - 1)

    if pairs:
        result.mean_displacement = sum(
            abs(pos_a[i] - pos_b[j]) for i, j in pairs
        ) / len(pairs)

    result.bigram_jaccard = _bigram_jaccard(seq_a, seq_b)
    return result


def _bigram_jaccard(seq_a: Sequence[int], seq_b: Sequence[int]) -> float:
    bigrams_a = {(seq_a[i], seq_a[i + 1]) for i in range(len(seq_a) - 1)}
    bigrams_b = {(seq_b[i], seq_b[i + 1]) for i in range(len(seq_b) - 1)}
    union = bigrams_a | bigrams_b
    if not union:
        return 0.0
    return len(bigrams_a & bigrams_b) / len(union)


def rubric_metrics(alignment: Alignment,
                   rubrics_a: Sequence[int], rubrics_b: Sequence[int]) -> RubricMetrics:
    """Agreement of rubric placement over position-matched occurrences.

    Only occurrences carrying a standardized rubric on *both* sides are compared;
    `coverage` says how large that subset was, so an agreement of 1.0 computed over
    three occurrences cannot be mistaken for a strong result.
    """
    pairs = alignment.positional_pairs
    result = RubricMetrics()
    if not pairs:
        return result

    comparable = [
        (rubrics_a[i], rubrics_b[j]) for i, j in pairs
        if rubrics_a[i] >= 0 and rubrics_b[j] >= 0
    ]
    result.coverage = len(comparable) / len(pairs)
    result.compared = len(comparable)
    if comparable:
        result.agreement = sum(1 for x, y in comparable if x == y) / len(comparable)
    return result


def compare(seq_a: Sequence[int], pos_a: Sequence[float], rubrics_a: Sequence[int],
            counts_a: Dict[int, int],
            seq_b: Sequence[int], pos_b: Sequence[float], rubrics_b: Sequence[int],
            counts_b: Dict[int, int],
            idf: Optional[Sequence[float]] = None) -> dict:
    """All three metric families for one pair, as a flat dict."""
    alignment = align(seq_a, pos_a, seq_b, pos_b)
    return {
        'content': asdict(content_metrics(counts_a, counts_b, idf)),
        'order': asdict(order_metrics(alignment, seq_a, pos_a, seq_b, pos_b)),
        'rubric': asdict(rubric_metrics(alignment, rubrics_a, rubrics_b)),
    }
