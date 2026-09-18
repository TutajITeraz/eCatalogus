"""Occurrence alignment between two manuscripts.

A formula can occur several times in one book, and which occurrence corresponds to
which matters. Taking the first occurrence on each side is wrong: the first one may
be an extra insertion while the *second* is the one standing in the same place as
the other manuscript's first. Both alignments here therefore work on full sequences
with repetitions.

Two complementary views:

* order — "what follows what". A longest common subsequence over the full
  sequences, computed with Hunt-Szymanski so that the cost stays near-linear when
  matches are sparse. Because it works on positions rather than on symbols, the
  second occurrence in A may legitimately match the first in B.
* position — "where it sits". For each formula, a monotone assignment between its
  occurrence lists minimising total displacement in normalized book position.
  This catches material standing in the same place even when the local order around
  it has been rearranged.

No function here touches Django; everything is plain Python and numpy.
"""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

#: Guard against a pathological symbol repeated hundreds of times on both sides,
#: which would make the Hunt-Szymanski match set quadratic. Well above anything
#: real liturgical data produces.
MAX_MATCH_PAIRS = 2_000_000


@dataclass
class Alignment:
    """Result of aligning two occurrence sequences."""

    #: Occurrence index pairs (i in A, j in B) forming a longest common subsequence.
    lcs_pairs: List[Tuple[int, int]] = field(default_factory=list)
    #: Occurrence index pairs matched by book position, per formula.
    positional_pairs: List[Tuple[int, int]] = field(default_factory=list)
    #: Multiset intersection size, sum over formulas of min(count_A, count_B).
    shared_occurrences: int = 0
    #: Distinct formulas present in both.
    shared_formulas: int = 0
    #: True when the match set had to be capped; metrics are then approximate.
    truncated: bool = False


def occurrence_positions(seq: Sequence[int]) -> Dict[int, List[int]]:
    """Formula -> ascending list of occurrence indices."""
    positions: Dict[int, List[int]] = defaultdict(list)
    for i, symbol in enumerate(seq):
        positions[symbol].append(i)
    return positions


def hunt_szymanski_lcs(seq_a: Sequence[int], seq_b: Sequence[int]) -> List[Tuple[int, int]]:
    """Longest common subsequence as index pairs, via Hunt-Szymanski.

    Cost is O((r + n) log n) with r the number of matching index pairs, rather than
    the O(n*m) of textbook dynamic programming. With formulas mostly occurring once
    or twice per manuscript, r stays close to the sequence length.
    """
    if not seq_a or not seq_b:
        return []

    b_positions = occurrence_positions(seq_b)
    # Descending, so that several occurrences of one symbol cannot chain onto
    # each other within a single step of the outer loop.
    b_positions_desc = {symbol: list(reversed(idx)) for symbol, idx in b_positions.items()}

    thresh: List[int] = []          # thresh[k]: smallest B index ending a match run of length k+1
    links: List[int] = []           # node id of that run's last match
    nodes: List[Tuple[int, int, int]] = []   # (i, j, previous node id or -1)

    for i, symbol in enumerate(seq_a):
        for j in b_positions_desc.get(symbol, ()):
            k = bisect_left(thresh, j)
            if k < len(thresh) and thresh[k] <= j:
                continue
            previous = links[k - 1] if k > 0 else -1
            nodes.append((i, j, previous))
            node_id = len(nodes) - 1
            if k == len(thresh):
                thresh.append(j)
                links.append(node_id)
            else:
                thresh[k] = j
                links[k] = node_id

    if not links:
        return []

    pairs: List[Tuple[int, int]] = []
    node_id = links[-1]
    while node_id != -1:
        i, j, previous = nodes[node_id]
        pairs.append((i, j))
        node_id = previous
    pairs.reverse()
    return pairs


def positional_matching(occ_a: Sequence[int], occ_b: Sequence[int],
                        pos_a: Sequence[float], pos_b: Sequence[float]
                        ) -> List[Tuple[int, int]]:
    """Monotone assignment between one formula's occurrence lists.

    Maximises the number of matched occurrences first (always min(len_a, len_b)),
    then minimises the total distance in normalized book position. Occurrence lists
    are short, so the quadratic table is free.
    """
    la, lb = len(occ_a), len(occ_b)
    if not la or not lb:
        return []

    # dp[i][j] = (-matches, cost); lexicographic minimum maximises matches first.
    best = [[(0, 0.0)] * (lb + 1) for _ in range(la + 1)]
    choice = [[0] * (lb + 1) for _ in range(la + 1)]   # 1 skip A, 2 skip B, 3 match

    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            skip_a = best[i - 1][j]
            skip_b = best[i][j - 1]
            prev = best[i - 1][j - 1]
            matched = (prev[0] - 1, prev[1] + abs(pos_a[occ_a[i - 1]] - pos_b[occ_b[j - 1]]))

            candidates = ((matched, 3), (skip_a, 1), (skip_b, 2))
            value, which = min(candidates, key=lambda c: c[0])
            best[i][j] = value
            choice[i][j] = which

    pairs: List[Tuple[int, int]] = []
    i, j = la, lb
    while i > 0 and j > 0:
        which = choice[i][j]
        if which == 3:
            pairs.append((occ_a[i - 1], occ_b[j - 1]))
            i -= 1
            j -= 1
        elif which == 1:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def align(seq_a: Sequence[int], pos_a: Sequence[float],
          seq_b: Sequence[int], pos_b: Sequence[float]) -> Alignment:
    """Full alignment of two manuscripts' occurrence sequences."""
    result = Alignment()
    if not seq_a or not seq_b:
        return result

    positions_a = occurrence_positions(seq_a)
    positions_b = occurrence_positions(seq_b)
    shared_symbols = positions_a.keys() & positions_b.keys()

    result.shared_formulas = len(shared_symbols)
    result.shared_occurrences = sum(
        min(len(positions_a[s]), len(positions_b[s])) for s in shared_symbols
    )
    if not result.shared_occurrences:
        return result

    match_pairs = sum(len(positions_a[s]) * len(positions_b[s]) for s in shared_symbols)
    if match_pairs > MAX_MATCH_PAIRS:
        result.truncated = True
        trimmed_a, trimmed_b = _trim_hot_symbols(seq_a, seq_b, positions_a, positions_b)
        result.lcs_pairs = hunt_szymanski_lcs(trimmed_a, trimmed_b)
    else:
        result.lcs_pairs = hunt_szymanski_lcs(seq_a, seq_b)

    for symbol in shared_symbols:
        result.positional_pairs.extend(positional_matching(
            positions_a[symbol], positions_b[symbol], pos_a, pos_b,
        ))
    result.positional_pairs.sort()

    return result


def _trim_hot_symbols(seq_a, seq_b, positions_a, positions_b, cap: int = 64):
    """Keep at most `cap` occurrences of any one symbol, evenly spread.

    Only reached by degenerate data; recorded as `truncated` on the result so the
    report can say the affected metrics are approximate.
    """
    def trim(seq, positions):
        drop = set()
        for symbol, occurrences in positions.items():
            if len(occurrences) <= cap:
                continue
            step = len(occurrences) / cap
            keep = {occurrences[int(i * step)] for i in range(cap)}
            drop.update(set(occurrences) - keep)
        return [s for i, s in enumerate(seq) if i not in drop]

    return trim(seq_a, positions_a), trim(seq_b, positions_b)


def count_inversions(values: Sequence[int]) -> int:
    """Number of out-of-order pairs, by merge sort."""
    working = list(values)
    buffer = [0] * len(working)
    return _sort_count(working, buffer, 0, len(working) - 1)


def _sort_count(values, buffer, low, high) -> int:
    if low >= high:
        return 0
    mid = (low + high) // 2
    total = _sort_count(values, buffer, low, mid) + _sort_count(values, buffer, mid + 1, high)

    i, j, k = low, mid + 1, low
    while i <= mid and j <= high:
        if values[i] <= values[j]:
            buffer[k] = values[i]
            i += 1
        else:
            buffer[k] = values[j]
            j += 1
            total += mid - i + 1
        k += 1
    while i <= mid:
        buffer[k] = values[i]
        i += 1
        k += 1
    while j <= high:
        buffer[k] = values[j]
        j += 1
        k += 1
    values[low:high + 1] = buffer[low:high + 1]
    return total
