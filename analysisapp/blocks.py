"""Blocks: runs of prayers that travel together.

A maximal contiguous run of formulas occurring in the same order in several
manuscripts is the most concrete thing this analysis can hand a liturgist — a
liturgical unit that moved through the tradition as one piece, rather than a
statistic about it.

Found by growing runs left to right and keeping only those still supported by
enough witnesses, so the search space collapses immediately: almost no length-2 run
survives, and the survivors are exactly the interesting ones.
"""

from collections import defaultdict
from typing import Dict, List, Tuple

from .cohort import CohortView

#: Longest run considered. Beyond this a "block" is really a whole section, and
#: the report is better served by the pairwise order metrics.
MAX_BLOCK_LENGTH = 25
#: A run must appear in at least this many manuscripts to count as shared.
MIN_SUPPORT = 3
#: Cap on how many blocks are written out, longest and best supported first.
MAX_BLOCKS = 500


def _support(occurrences: List[Tuple[int, int]]) -> int:
    return len({ms_index for ms_index, _start in occurrences})


def find_blocks(view: CohortView,
                min_support: int = MIN_SUPPORT,
                max_length: int = MAX_BLOCK_LENGTH,
                max_blocks: int = MAX_BLOCKS) -> List[dict]:
    """Maximal formula runs shared by at least `min_support` manuscripts."""
    sequences = view.seqs
    if view.n_manuscripts < min_support:
        return []

    level: Dict[Tuple[int, ...], List[Tuple[int, int]]] = defaultdict(list)
    for ms_index, seq in enumerate(sequences):
        for start in range(len(seq) - 1):
            level[(seq[start], seq[start + 1])].append((ms_index, start))
    level = {run: occ for run, occ in level.items() if _support(occ) >= min_support}

    results: List[dict] = []
    length = 2
    while level and length < max_length:
        extended: Dict[Tuple[int, ...], List[Tuple[int, int]]] = defaultdict(list)
        for run, occurrences in level.items():
            for ms_index, start in occurrences:
                seq = sequences[ms_index]
                end = start + length
                if end < len(seq):
                    extended[run + (seq[end],)].append((ms_index, start))
        extended = {run: occ for run, occ in extended.items() if _support(occ) >= min_support}

        # A run is maximal only if neither growing it right nor growing it left
        # keeps the same number of witnesses.
        right_support: Dict[Tuple[int, ...], int] = defaultdict(int)
        for run, occurrences in extended.items():
            right_support[run[:-1]] = max(right_support[run[:-1]], _support(occurrences))

        for run, occurrences in level.items():
            support = _support(occurrences)
            if right_support.get(run, 0) >= support:
                continue
            if _left_extension_keeps_support(run, occurrences, sequences, support):
                continue
            results.append(_describe(view, run, occurrences, support))

        level = extended
        length += 1

    # Whatever survived to the length cap is maximal for our purposes.
    for run, occurrences in level.items():
        support = _support(occurrences)
        if not _left_extension_keeps_support(run, occurrences, sequences, support):
            results.append(_describe(view, run, occurrences, support))

    results.sort(key=lambda b: (-b['length'], -b['support']))
    return results[:max_blocks]


def _left_extension_keeps_support(run, occurrences, sequences, support) -> bool:
    """True when one symbol on the left precedes the run in every witness.

    Such a run is only the tail of a longer shared block, and reporting it would
    bury the real block under its own suffixes.
    """
    by_symbol: Dict[int, set] = defaultdict(set)
    for ms_index, start in occurrences:
        if start > 0:
            by_symbol[sequences[ms_index][start - 1]].add(ms_index)
    return any(len(witnesses) >= support for witnesses in by_symbol.values())


def _describe(view: CohortView, run, occurrences, support) -> dict:
    witnesses = sorted({ms_index for ms_index, _ in occurrences})
    positions = [
        view.positions[ms_index][start] for ms_index, start in occurrences
    ]
    formulas = []
    for local in run:
        meta = view.formula_meta(local)
        formulas.append({
            'uuid': meta.uuid,
            'co_no': meta.co_no,
            'incipit': meta.incipit,
            'traditions': [view.corpus.traditions[t].name for t in meta.tradition_indices],
        })

    return {
        'length': len(run),
        'support': support,
        'occurrences': len(occurrences),
        'manuscripts': [
            {'uuid': view.manuscripts[i].uuid, 'label': view.manuscripts[i].label}
            for i in witnesses
        ],
        'mean_position': round(sum(positions) / len(positions), 4) if positions else None,
        'formulas': formulas,
    }
