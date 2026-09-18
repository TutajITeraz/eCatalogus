"""A cohort: the slice of the corpus one set of matrices is computed over.

Formulas are re-indexed locally, so document frequency and idf are relative to the
cohort rather than the whole corpus. That matters: a formula common in every
sacramentary but absent from antiphonaries should look ordinary inside the
sacramentary cohort and distinctive in the global one.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .extract import Corpus, ManuscriptProfile


@dataclass
class CohortView:
    slug: str
    label: str
    corpus: Corpus
    manuscripts: List[ManuscriptProfile]

    #: Global formula indices present in this cohort, ascending.
    formula_ids: List[int] = field(default_factory=list)
    #: Global formula index -> local index.
    local_of_global: Dict[int, int] = field(default_factory=dict)

    #: Per manuscript, the occurrence sequence in *local* formula indices.
    seqs: List[List[int]] = field(default_factory=list)
    #: Per manuscript, the normalized position of each occurrence.
    positions: List[List[float]] = field(default_factory=list)
    #: Per manuscript, the rubric index of each occurrence (-1 when absent).
    rubrics: List[List[int]] = field(default_factory=list)
    #: Per manuscript, local formula index -> occurrence count.
    counts: List[Dict[int, int]] = field(default_factory=list)

    @property
    def n_manuscripts(self) -> int:
        return len(self.manuscripts)

    @property
    def n_formulas(self) -> int:
        return len(self.formula_ids)

    def formula_meta(self, local_index: int):
        return self.corpus.formulas[self.formula_ids[local_index]]

    def document_frequency(self) -> np.ndarray:
        """How many manuscripts each formula appears in."""
        df = np.zeros(self.n_formulas, dtype=np.int32)
        for counts in self.counts:
            for local in counts:
                df[local] += 1
        return df

    def idf(self) -> np.ndarray:
        """Smoothed inverse document frequency.

        A formula in every witness carries almost no evidential weight; a formula
        shared by two witnesses out of eighty carries a lot. The +1 terms keep the
        value finite and strictly positive at both extremes.
        """
        df = self.document_frequency().astype(np.float64)
        n = float(self.n_manuscripts)
        return np.log((n + 1.0) / (df + 1.0)) + 1.0

    def incidence_matrix(self, binary: bool = False) -> np.ndarray:
        """Manuscripts x formulas, counts by default."""
        matrix = np.zeros((self.n_manuscripts, self.n_formulas), dtype=np.float64)
        for i, counts in enumerate(self.counts):
            for local, value in counts.items():
                matrix[i, local] = 1.0 if binary else float(value)
        return matrix


def build_cohort_view(corpus: Corpus, slug: str, label: str, indices) -> CohortView:
    manuscripts = [corpus.manuscripts[i] for i in indices]

    present = sorted({f for ms in manuscripts for f in ms.counts})
    local_of_global = {global_idx: local for local, global_idx in enumerate(present)}

    view = CohortView(
        slug=slug,
        label=label,
        corpus=corpus,
        manuscripts=manuscripts,
        formula_ids=present,
        local_of_global=local_of_global,
    )

    for ms in manuscripts:
        seq = [local_of_global[f] for f in ms.formula_seq]
        view.seqs.append(seq)
        view.positions.append(list(ms.position_seq))
        view.rubrics.append(list(ms.rubric_seq))

        counts = defaultdict(int)
        for local in seq:
            counts[local] += 1
        view.counts.append(dict(counts))

    return view
