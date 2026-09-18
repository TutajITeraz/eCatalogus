"""Unit tests for the analytical core.

All of these run without a database: the metric and alignment layers deliberately
take plain sequences, so they can be checked against values worked out by hand.
"""

from django.test import SimpleTestCase

from analysisapp.align import (
    align,
    count_inversions,
    hunt_szymanski_lcs,
    positional_matching,
)
from analysisapp.metrics import (
    content_metrics,
    order_metrics,
    rubric_metrics,
)


def positions(seq):
    """Normalized positions matching what extract.py assigns."""
    denominator = max(len(seq) - 1, 1)
    return [i / denominator for i in range(len(seq))]


class HuntSzymanskiTests(SimpleTestCase):

    def test_longest_common_subsequence_length(self):
        pairs = hunt_szymanski_lcs([1, 2, 3, 4], [2, 1, 3, 4])
        self.assertEqual(len(pairs), 3)
        # Indices must be strictly increasing on both sides.
        self.assertEqual([i for i, _ in pairs], sorted(i for i, _ in pairs))
        self.assertEqual([j for _, j in pairs], sorted(j for _, j in pairs))

    def test_identical_sequences_match_fully(self):
        seq = [5, 6, 7, 8]
        self.assertEqual(hunt_szymanski_lcs(seq, seq), [(0, 0), (1, 1), (2, 2), (3, 3)])

    def test_disjoint_sequences_have_no_matches(self):
        self.assertEqual(hunt_szymanski_lcs([1, 2], [3, 4]), [])

    def test_empty_input(self):
        self.assertEqual(hunt_szymanski_lcs([], [1]), [])
        self.assertEqual(hunt_szymanski_lcs([1], []), [])

    def test_first_occurrence_may_be_the_extra_one(self):
        """The core reason alignment works on occurrences, not on formulas.

        In A the formula F occurs twice: an inserted copy at the very start, and the
        one that really corresponds to B's single F. Pairing first-with-first would
        report the material as heavily displaced; the alignment must instead match
        A's *second* F.
        """
        F, a, b, c, d = 100, 1, 2, 3, 4
        seq_a = [F, a, b, F, c, d]
        seq_b = [a, b, F, c, d]

        result = align(seq_a, positions(seq_a), seq_b, positions(seq_b))

        # The whole of B is recovered in order, which is only possible if A's
        # second F (index 3) is the one matched to B's F (index 2).
        self.assertEqual(result.lcs_pairs, [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4)])

        f_matches = [pair for pair in result.positional_pairs if seq_a[pair[0]] == F]
        self.assertEqual(f_matches, [(3, 2)])


class PositionalMatchingTests(SimpleTestCase):

    def test_picks_the_nearest_occurrence(self):
        # One occurrence in B, two in A; the closer one in book position wins.
        pos_a = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        pos_b = [0.0, 0.25, 0.5, 0.75, 1.0]
        self.assertEqual(positional_matching([0, 3], [2], pos_a, pos_b), [(3, 2)])

    def test_matching_is_monotone(self):
        pos_a = [0.0, 0.5, 1.0]
        pos_b = [0.0, 0.5, 1.0]
        pairs = positional_matching([0, 1, 2], [0, 2], pos_a, pos_b)
        self.assertEqual(len(pairs), 2)
        self.assertEqual([i for i, _ in pairs], sorted(i for i, _ in pairs))
        self.assertEqual([j for _, j in pairs], sorted(j for _, j in pairs))

    def test_matches_as_many_as_possible(self):
        pos = [0.0, 0.5, 1.0]
        self.assertEqual(len(positional_matching([0, 1, 2], [0, 1], pos, pos)), 2)


class InversionTests(SimpleTestCase):

    def test_sorted_has_none(self):
        self.assertEqual(count_inversions([0, 1, 2, 3]), 0)

    def test_reversed_has_all(self):
        self.assertEqual(count_inversions([3, 2, 1, 0]), 6)

    def test_single_swap(self):
        self.assertEqual(count_inversions([0, 2, 1, 3]), 1)


class ContentMetricTests(SimpleTestCase):

    def test_hand_computed_values(self):
        result = content_metrics({1: 1, 2: 1, 3: 1}, {2: 1, 3: 1, 4: 1})
        self.assertAlmostEqual(result.jaccard, 0.5)
        self.assertAlmostEqual(result.weighted_jaccard, 0.5)
        self.assertAlmostEqual(result.containment, 2 / 3)
        self.assertEqual(result.shared_formulas, 2)
        self.assertEqual(result.only_a, 1)
        self.assertEqual(result.only_b, 1)

    def test_weighted_jaccard_sees_repetition_that_jaccard_misses(self):
        result = content_metrics({1: 3, 2: 1}, {1: 1, 2: 1})
        self.assertAlmostEqual(result.jaccard, 1.0)
        self.assertAlmostEqual(result.containment, 1.0)
        self.assertAlmostEqual(result.weighted_jaccard, 0.5)

    def test_containment_recognises_a_contained_fragment(self):
        fragment = {1: 1, 2: 1}
        codex = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1}
        result = content_metrics(fragment, codex)
        self.assertAlmostEqual(result.containment, 1.0)
        self.assertAlmostEqual(result.jaccard, 0.25)

    def test_idf_cosine_separates_pairs_that_jaccard_cannot(self):
        """Sharing a rare oration must outweigh sharing a ubiquitous one."""
        idf = [3.0, 1.0, 1.0, 1.0]        # formula 0 is rare, the rest are common
        rare_share = content_metrics({0: 1, 1: 1}, {0: 1, 2: 1}, idf)
        common_share = content_metrics({0: 1, 1: 1}, {1: 1, 3: 1}, idf)

        self.assertAlmostEqual(rare_share.jaccard, 1 / 3)
        self.assertAlmostEqual(common_share.jaccard, 1 / 3)
        self.assertAlmostEqual(rare_share.idf_cosine, 0.9)
        self.assertAlmostEqual(common_share.idf_cosine, 1 / (10 ** 0.5 * 2 ** 0.5))
        self.assertGreater(rare_share.idf_cosine, common_share.idf_cosine)

    def test_empty_inputs(self):
        result = content_metrics({}, {})
        self.assertEqual(result.jaccard, 0.0)
        self.assertEqual(result.shared_formulas, 0)


class OrderMetricTests(SimpleTestCase):

    def _metrics(self, seq_a, seq_b):
        pos_a, pos_b = positions(seq_a), positions(seq_b)
        alignment = align(seq_a, pos_a, seq_b, pos_b)
        return alignment, order_metrics(alignment, seq_a, pos_a, seq_b, pos_b)

    def test_identical_sequences(self):
        _, result = self._metrics([1, 2, 3, 4], [1, 2, 3, 4])
        self.assertAlmostEqual(result.nlcs, 1.0)
        self.assertAlmostEqual(result.kendall_tau_b, 1.0)
        self.assertAlmostEqual(result.breakpoint_rate, 1.0)
        self.assertAlmostEqual(result.mean_displacement, 0.0)
        self.assertAlmostEqual(result.bigram_jaccard, 1.0)

    def test_reversed_sequences(self):
        _, result = self._metrics([1, 2, 3, 4], [4, 3, 2, 1])
        self.assertAlmostEqual(result.nlcs, 0.25)
        self.assertAlmostEqual(result.kendall_tau_b, -1.0)
        self.assertAlmostEqual(result.breakpoint_rate, 0.0)
        self.assertAlmostEqual(result.mean_displacement, 2 / 3)
        self.assertAlmostEqual(result.bigram_jaccard, 0.0)

    def test_breakpoint_rate_counts_preserved_neighbours(self):
        # One insertion on each side breaks exactly one adjacency out of four.
        _, result = self._metrics([1, 2, 3, 9, 4, 5], [8, 1, 2, 3, 4, 5])
        self.assertEqual(result.matched_occurrences, 5)
        self.assertAlmostEqual(result.breakpoint_rate, 0.75)

    def test_no_shared_material(self):
        _, result = self._metrics([1, 2], [3, 4])
        self.assertEqual(result.nlcs, 0.0)
        self.assertEqual(result.matched_occurrences, 0)
        self.assertEqual(result.kendall_tau_b, 0.0)

    def test_formula_repeated_five_times(self):
        alignment, result = self._metrics([1, 1, 1, 1, 1], [1, 1])
        self.assertEqual(alignment.shared_occurrences, 2)
        self.assertEqual(result.lcs_length, 2)
        self.assertAlmostEqual(result.nlcs, 1.0)

    def test_single_item_manuscript(self):
        alignment, result = self._metrics([1], [1, 2, 3])
        self.assertEqual(alignment.shared_occurrences, 1)
        self.assertAlmostEqual(result.nlcs, 1.0)
        # A single matched occurrence gives no ordering evidence either way.
        self.assertEqual(result.kendall_tau_b, 0.0)


class RubricMetricTests(SimpleTestCase):

    def test_agreement_and_coverage(self):
        seq = [1, 2, 3]
        pos = positions(seq)
        alignment = align(seq, pos, seq, pos)

        # Third occurrence has no standardized rubric on side A, so it is excluded.
        result = rubric_metrics(alignment, [0, 1, -1], [0, 2, 5])
        self.assertEqual(result.compared, 2)
        self.assertAlmostEqual(result.coverage, 2 / 3)
        self.assertAlmostEqual(result.agreement, 0.5)

    def test_no_rubrics_at_all(self):
        """Today's data: rubric_uuid is empty everywhere. Report it, do not crash."""
        seq = [1, 2, 3]
        pos = positions(seq)
        alignment = align(seq, pos, seq, pos)

        result = rubric_metrics(alignment, [-1, -1, -1], [-1, -1, -1])
        self.assertEqual(result.compared, 0)
        self.assertEqual(result.coverage, 0.0)
        self.assertEqual(result.agreement, 0.0)


# ---------------------------------------------------------------------------
# Cohort, blocks and exports
# ---------------------------------------------------------------------------

import numpy as np
from django.test import TestCase

from analysisapp import blocks as blocks_module
from analysisapp import ms_space
from analysisapp.cohort import build_cohort_view
from analysisapp.extract import Corpus, FormulaMeta, ManuscriptProfile, TraditionMeta


def make_corpus(sequences, traditions=None, formula_traditions=None):
    """A corpus from plain lists of formula indices, with no database involved."""
    n_formulas = max(max(seq) for seq in sequences) + 1
    formulas = [
        FormulaMeta(index=i, pk=i, uuid=f'formula-{i}', co_no=f'CO{i}', incipit=f'Incipit {i}')
        for i in range(n_formulas)
    ]
    for index, tradition_indices in (formula_traditions or {}).items():
        formulas[index].tradition_indices = list(tradition_indices)

    tradition_metas = [
        TraditionMeta(index=i, pk=i, uuid=f'tradition-{i}', name=name,
                      color_rgb=None, genre_uuid=None)
        for i, name in enumerate(traditions or [])
    ]

    manuscripts = []
    for m, seq in enumerate(sequences):
        profile = ManuscriptProfile(
            index=m, pk=m, uuid=f'ms-{m}', label=f'MS {m}', shelf_mark=None,
            common_name=None, genre_uuids=[], year_from=None, year_to=None,
            century_from=None, century_to=None,
        )
        denominator = max(len(seq) - 1, 1)
        profile.formula_seq = list(seq)
        profile.position_seq = [i / denominator for i in range(len(seq))]
        profile.rubric_seq = [-1] * len(seq)
        profile.occ_index_seq = [0] * len(seq)
        counts = {}
        for formula in seq:
            counts[formula] = counts.get(formula, 0) + 1
        profile.counts = counts
        manuscripts.append(profile)

    return Corpus(manuscripts=manuscripts, formulas=formulas,
                  traditions=tradition_metas, rubrics=[])


def make_view(sequences, **kwargs):
    corpus = make_corpus(sequences, **kwargs)
    return build_cohort_view(corpus, 'test', 'Test cohort',
                             list(range(len(corpus.manuscripts))))


class NormalizeRowsTests(SimpleTestCase):

    def test_rows_sum_to_one(self):
        result = ms_space.normalize_rows(np.array([[1.0, 3.0], [2.0, 2.0]]))
        self.assertAlmostEqual(result[0, 0], 0.25)
        self.assertAlmostEqual(result[1, 0], 0.5)

    def test_all_zero_row_stays_zero(self):
        """Guards the np.divide(where=...) trap: without an explicit `out`, the
        masked entries come back as uninitialised memory, not zeros."""
        result = ms_space.normalize_rows(np.array([[0.0, 0.0], [1.0, 1.0]]))
        self.assertEqual(result[0].tolist(), [0.0, 0.0])
        self.assertAlmostEqual(result[1, 0], 0.5)


class CohortViewTests(SimpleTestCase):

    def test_document_frequency_and_incidence(self):
        view = make_view([[0, 1, 1, 2], [1, 2], [2]])
        self.assertEqual(view.n_manuscripts, 3)
        self.assertEqual(view.n_formulas, 3)
        self.assertEqual(view.document_frequency().tolist(), [1, 2, 3])
        self.assertEqual(view.incidence_matrix()[0].tolist(), [1.0, 2.0, 1.0])
        self.assertEqual(view.incidence_matrix(binary=True)[0].tolist(), [1.0, 1.0, 1.0])

    def test_idf_rewards_rarity(self):
        view = make_view([[0, 1, 1, 2], [1, 2], [2]])
        idf = view.idf()
        self.assertGreater(idf[0], idf[1])
        self.assertGreater(idf[1], idf[2])

    def test_formulas_are_reindexed_to_the_cohort(self):
        corpus = make_corpus([[0, 1], [5, 6]])
        view = build_cohort_view(corpus, 'sub', 'Subset', [1])
        self.assertEqual(view.formula_ids, [5, 6])
        self.assertEqual(view.seqs, [[0, 1]])


class BlockTests(SimpleTestCase):

    def test_finds_a_run_shared_by_three_witnesses(self):
        view = make_view([
            [9, 1, 2, 3, 4, 8],
            [7, 1, 2, 3, 4],
            [1, 2, 3, 4, 6],
        ])
        found = blocks_module.find_blocks(view, min_support=3)
        self.assertTrue(found)
        longest = found[0]
        self.assertEqual(longest['length'], 4)
        self.assertEqual(longest['support'], 3)
        self.assertEqual([f['co_no'] for f in longest['formulas']],
                         ['CO1', 'CO2', 'CO3', 'CO4'])

    def test_suffixes_of_a_block_are_not_reported_separately(self):
        view = make_view([[1, 2, 3], [1, 2, 3], [1, 2, 3]])
        found = blocks_module.find_blocks(view, min_support=3)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['length'], 3)

    def test_nothing_shared_widely_enough(self):
        view = make_view([[1, 2], [3, 4], [5, 6]])
        self.assertEqual(blocks_module.find_blocks(view, min_support=3), [])


class ExportTests(SimpleTestCase):

    def _space(self):
        view = make_view([[0, 1, 2, 3], [0, 1, 2, 4], [5, 6, 7, 8], [5, 6, 7, 9]])
        space = ms_space.compute_matrices(view)
        return view, ms_space.cluster_manuscripts(view, space)

    def test_newick_is_balanced_and_names_every_leaf(self):
        view, space = self._space()
        newick = ms_space.to_newick(space.linkage, [m.label for m in view.manuscripts])
        self.assertTrue(newick.endswith(';'))
        self.assertEqual(newick.count('('), newick.count(')'))
        for manuscript in view.manuscripts:
            self.assertIn(manuscript.label, newick)

    def test_nexus_declares_the_right_number_of_taxa(self):
        view, space = self._space()
        distance = 1.0 - space.matrices['idf_cosine']
        nexus = ms_space.to_nexus(distance, [m.label for m in view.manuscripts])
        self.assertIn('#NEXUS', nexus)
        self.assertIn('ntax=4', nexus)
        self.assertIn('BEGIN distances;', nexus)

    def test_nexus_makes_duplicate_labels_unique(self):
        nexus = ms_space.to_nexus(np.zeros((2, 2)), ['Same name', 'Same name'])
        self.assertIn('Same_name', nexus)
        self.assertIn('Same_name_1', nexus)

    def test_similar_manuscripts_are_adjacent_after_seriation(self):
        """The two halves of the corpus share nothing, so seriation must not
        interleave them."""
        view, space = self._space()
        order = space.leaf_order
        first_pair = sorted(order[:2])
        self.assertIn(first_pair, ([0, 1], [2, 3]))


class ManuscriptMetricTests(SimpleTestCase):

    def test_identical_manuscripts_score_one(self):
        view = make_view([[0, 1, 2], [0, 1, 2]])
        space = ms_space.compute_matrices(view)
        for metric in ('jaccard', 'idf_cosine', 'containment', 'nlcs'):
            self.assertAlmostEqual(space.matrices[metric][0, 1], 1.0, places=6,
                                   msg=f'{metric} should be 1.0 for identical witnesses')

    def test_disjoint_manuscripts_score_zero(self):
        view = make_view([[0, 1, 2], [3, 4, 5]])
        space = ms_space.compute_matrices(view)
        for metric in ('jaccard', 'idf_cosine', 'containment', 'nlcs'):
            self.assertAlmostEqual(space.matrices[metric][0, 1], 0.0, places=6)

    def test_matrices_are_symmetric_with_unit_diagonal(self):
        view = make_view([[0, 1, 2, 3], [1, 2], [2, 3, 4]])
        space = ms_space.compute_matrices(view)
        for metric, matrix in space.matrices.items():
            self.assertTrue(np.allclose(matrix, matrix.T), f'{metric} is not symmetric')
            self.assertTrue(np.allclose(np.diag(matrix), 1.0), f'{metric} diagonal')

    def test_containment_beats_jaccard_for_a_fragment(self):
        view = make_view([[0, 1], [0, 1, 2, 3, 4, 5, 6, 7]])
        space = ms_space.compute_matrices(view)
        self.assertAlmostEqual(space.matrices['containment'][0, 1], 1.0)
        self.assertAlmostEqual(space.matrices['jaccard'][0, 1], 0.25)

    def test_single_manuscript_cohort_does_not_crash(self):
        view = make_view([[0, 1, 2]])
        space = ms_space.compute_matrices(view)
        self.assertTrue(space.notes)
        ms_space.cluster_manuscripts(view, space)
        self.assertEqual(space.leaf_order, [0])


class ExtractionTests(TestCase):
    """The ORM layer, against a real (test) database.

    Covers the parts that plain sequences cannot: ordering by sequence_in_ms,
    repetition counting, the min_items threshold and rubric coverage reporting.
    """

    @classmethod
    def setUpTestData(cls):
        from indexerapp.models import Content, Formulas, Manuscripts

        cls.formulas = [
            Formulas.objects.create(uuid=f'00000000-0000-4000-8000-00000000000{i}',
                                    co_no=f'CO{i}', text=f'Oratio {i}')
            for i in range(1, 6)
        ]
        cls.big = Manuscripts.objects.create(
            uuid='10000000-0000-4000-8000-000000000001', name='Big codex', shelf_mark='MS 1')
        cls.small = Manuscripts.objects.create(
            uuid='10000000-0000-4000-8000-000000000002', name='Thin witness', shelf_mark='MS 2')

        rows = []
        # Deliberately inserted out of order, and with formula 1 occurring twice.
        for sequence, formula in [(30, 0), (10, 0), (20, 1), (40, 2), (50, 3)]:
            rows.append(Content(manuscript_uuid=cls.big, formula_uuid=cls.formulas[formula],
                                sequence_in_ms=sequence, where_in_ms_from=''))
        for sequence, formula in [(10, 0), (20, 4)]:
            rows.append(Content(manuscript_uuid=cls.small, formula_uuid=cls.formulas[formula],
                                sequence_in_ms=sequence, where_in_ms_from=''))
        Content.objects.bulk_create(rows)

    def test_occurrences_are_ordered_by_sequence_in_ms(self):
        from analysisapp.extract import load_corpus

        corpus = load_corpus(min_items=1)
        big = next(m for m in corpus.manuscripts if m.label.startswith('Big'))
        order = [corpus.formulas[i].co_no for i in big.formula_seq]
        self.assertEqual(order, ['CO1', 'CO2', 'CO1', 'CO3', 'CO4'])

    def test_repetitions_are_counted_not_collapsed(self):
        from analysisapp.extract import load_corpus

        corpus = load_corpus(min_items=1)
        big = next(m for m in corpus.manuscripts if m.label.startswith('Big'))
        self.assertEqual(big.n_items, 5)
        self.assertEqual(big.n_distinct, 4)
        self.assertEqual(max(big.counts.values()), 2)

    def test_positions_span_the_whole_book(self):
        from analysisapp.extract import load_corpus

        corpus = load_corpus(min_items=1)
        big = next(m for m in corpus.manuscripts if m.label.startswith('Big'))
        self.assertAlmostEqual(big.position_seq[0], 0.0)
        self.assertAlmostEqual(big.position_seq[-1], 1.0)

    def test_min_items_skips_thin_witnesses_and_records_why(self):
        from analysisapp.extract import load_corpus

        corpus = load_corpus(min_items=4)
        self.assertEqual(corpus.n_manuscripts, 1)
        self.assertEqual(corpus.skipped_manuscripts[0]['reason'], 'below_min_items')
        self.assertEqual(corpus.skipped_manuscripts[0]['n_items'], 2)

    def test_rubric_coverage_is_zero_without_standardized_rubrics(self):
        from analysisapp.extract import load_corpus

        corpus = load_corpus(min_items=1)
        self.assertEqual(corpus.rubric_coverage, 0.0)


class PipelineTests(TestCase):
    """End to end: from database rows to artifacts on disk."""

    @classmethod
    def setUpTestData(cls):
        from indexerapp.models import Content, Formulas, Manuscripts

        formulas = [
            Formulas.objects.create(uuid=f'20000000-0000-4000-8000-0000000000{i:02d}',
                                    co_no=f'CO{i}', text=f'Oratio {i}')
            for i in range(20)
        ]
        # Three witnesses sharing a core, each with its own tail.
        plans = [(0, list(range(0, 12))), (1, list(range(0, 10)) + [12, 13, 14]),
                 (2, list(range(0, 9)) + [15, 16, 17, 18])]
        rows = []
        for index, formula_indices in plans:
            manuscript = Manuscripts.objects.create(
                uuid=f'30000000-0000-4000-8000-00000000000{index}',
                name=f'Witness {index}', shelf_mark=f'MS {index}')
            for sequence, formula_index in enumerate(formula_indices):
                rows.append(Content(
                    manuscript_uuid=manuscript, formula_uuid=formulas[formula_index],
                    sequence_in_ms=sequence + 1, where_in_ms_from=''))
        Content.objects.bulk_create(rows)

    def test_run_produces_readable_artifacts(self):
        import json
        import os

        from analysisapp.models import AnalysisArtifact, AnalysisRun
        from analysisapp.pipeline import execute_run

        run = AnalysisRun.objects.create(params={'min_items': 5, 'min_block_support': 3})
        manifest = execute_run(run)

        run.refresh_from_db()
        self.assertEqual(run.status, AnalysisRun.STATUS_DONE)
        self.assertEqual(run.progress, 100)
        self.assertEqual(manifest['cohorts'][0]['manuscripts'], 3)

        kinds = set(AnalysisArtifact.objects.filter(run=run).values_list('kind', flat=True))
        for required in ('manifest', 'report', 'matrices', 'manuscripts', 'formulas',
                         'presence', 'blocks', 'rubrics', 'formula_embedding'):
            self.assertIn(required, kinds)

        for artifact in AnalysisArtifact.objects.filter(run=run).exclude(
                kind__in=('nexus', 'newick')):
            self.assertTrue(os.path.exists(artifact.absolute_path), artifact.kind)
            with open(artifact.absolute_path, encoding='utf-8') as handle:
                json.load(handle)          # must be valid JSON, not just present

    def test_report_names_the_shared_block_and_the_missing_rubrics(self):
        from analysisapp.models import AnalysisRun
        from analysisapp.pipeline import execute_run
        import json

        run = AnalysisRun.objects.create(params={'min_items': 5, 'min_block_support': 3})
        execute_run(run)

        artifact = run.artifacts.get(cohort='all', kind='report')
        with open(artifact.absolute_path, encoding='utf-8') as handle:
            report = json.load(handle)

        sections = {section['id']: section for section in report['sections']}
        self.assertIn('order', sections)
        self.assertIn('caveats', sections)
        # The nine formulas every witness shares must surface as one block.
        self.assertTrue(any('9 prayers' in p or 'longest shared run' in p
                            for p in sections['order']['paragraphs']))
        self.assertTrue(any('rubric' in p.lower() for p in sections['caveats']['paragraphs']))

    def test_failure_is_recorded_on_the_run(self):
        from analysisapp.models import AnalysisRun
        from analysisapp.pipeline import execute_run

        run = AnalysisRun.objects.create(params={'min_items': 10000})
        with self.assertRaises(ValueError):
            execute_run(run)

        run.refresh_from_db()
        self.assertEqual(run.status, AnalysisRun.STATUS_FAILED)
        self.assertIn('min_items', run.error)
