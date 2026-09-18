"""Rubric stability: does a prayer always stand under the same rubric?

For each formula we collect the rubrics it appears under across the comparison group. A
prayer that always falls under one rubric is an *anchor* — liturgically fixed. One
that appears under many is a *floater*, reusable material that moved between rites.
The distinction is usually more telling than the raw counts.

The rubric key is `content.rubric_uuid` and nothing else (see
`extract.resolve_rubric_key`). That column is currently empty in the data, so this
module is written to report its own emptiness rather than to fail or, worse, to
produce confident-looking output from three stray rows.
"""

import math
from collections import Counter, defaultdict
from typing import List

from .cohort import CohortView

#: Witnesses required before a formula's rubric behaviour is worth reporting.
MIN_WITNESSES = 3
#: How many anchors and floaters to list.
TOP_N = 100


def analyse(view: CohortView) -> dict:
    """Rubric distribution per formula, plus group-level coverage."""
    total_occurrences = sum(len(seq) for seq in view.seqs)
    covered = sum(1 for rubrics in view.rubrics for r in rubrics if r >= 0)
    coverage = covered / total_occurrences if total_occurrences else 0.0

    if not covered:
        return {
            'coverage': 0.0,
            'total_occurrences': total_occurrences,
            'covered_occurrences': 0,
            'available': False,
            'note': (
                'No content row in this comparison group carries a standardized rubric '
                '(content.rubric_uuid). Rubric stability cannot be assessed until '
                'that column is filled; the raw rubric_name_from_ms text is '
                'deliberately not used as a substitute.'
            ),
            'formulas': [],
            'anchors': [],
            'floaters': [],
        }

    # formula -> rubric -> set of manuscripts
    observations = defaultdict(lambda: defaultdict(set))
    for ms_index, (seq, rubrics) in enumerate(zip(view.seqs, view.rubrics)):
        for local, rubric in zip(seq, rubrics):
            if rubric >= 0:
                observations[local][rubric].add(ms_index)

    records: List[dict] = []
    for local, by_rubric in observations.items():
        witnesses = len({ms for members in by_rubric.values() for ms in members})
        counts = Counter({rubric: len(members) for rubric, members in by_rubric.items()})
        total = sum(counts.values())
        modal_rubric, modal_hits = counts.most_common(1)[0]
        meta = view.formula_meta(local)

        records.append({
            'formula_uuid': meta.uuid,
            'co_no': meta.co_no,
            'incipit': meta.incipit,
            'witnesses': witnesses,
            'distinct_rubrics': len(counts),
            'modal_rubric': view.corpus.rubrics[modal_rubric].name,
            'modal_rubric_uuid': view.corpus.rubrics[modal_rubric].uuid,
            'modal_share': round(modal_hits / total, 4) if total else 0.0,
            'entropy': round(_entropy(counts.values(), total), 4),
            'distribution': {
                view.corpus.rubrics[rubric].name: count
                for rubric, count in counts.most_common()
            },
        })

    records.sort(key=lambda r: (-r['witnesses'], r['co_no']))
    reliable = [r for r in records if r['witnesses'] >= MIN_WITNESSES]

    anchors = [r for r in reliable if r['modal_share'] == 1.0]
    anchors.sort(key=lambda r: -r['witnesses'])
    floaters = sorted(reliable, key=lambda r: (-r['entropy'], -r['witnesses']))

    return {
        'coverage': round(coverage, 4),
        'total_occurrences': total_occurrences,
        'covered_occurrences': covered,
        'available': True,
        'min_witnesses': MIN_WITNESSES,
        'formulas_with_rubrics': len(records),
        'formulas_above_threshold': len(reliable),
        'formulas': records,
        'anchors': anchors[:TOP_N],
        'floaters': [r for r in floaters if r['entropy'] > 0][:TOP_N],
    }


def _entropy(counts, total: int) -> float:
    """Shannon entropy in bits; 0 when a formula never leaves its rubric."""
    if not total:
        return 0.0
    result = 0.0
    for count in counts:
        if count <= 0:
            continue
        p = count / total
        result -= p * math.log2(p)
    return result
