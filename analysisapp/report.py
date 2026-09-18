"""The research document.

Produces `report.json`: a structured set of findings that the page renders and the
browser prints. Nothing here formats HTML — the display layer owns presentation,
this layer owns what is worth saying.

The caveats section is not decoration. Several things in this data can make a
result look stronger than it is, above all the fact that some witnesses in the
corpus are the very editions the traditions were defined from, and the report is
required to say so.
"""

import math
from typing import List, Optional

import numpy as np

from .cohort import CohortView
from .ms_space import normalize_rows

#: A formula present in at least this share of the comparison group counts as core repertoire.
CORE_THRESHOLD = 0.8
#: How many rows any one table in the report may carry.
TABLE_LIMIT = 50


def _section(section_id, title, paragraphs=None, tables=None, highlights=None):
    return {
        'id': section_id,
        'title': title,
        'paragraphs': paragraphs or [],
        'tables': tables or [],
        'highlights': highlights or [],
    }


def _table(title, columns, rows, note=None):
    return {'title': title, 'columns': columns, 'rows': rows[:TABLE_LIMIT], 'note': note}


def build(view: CohortView, formula_space, manuscript_space,
          block_list: List[dict], rubric_analysis: dict,
          exemplars: List[dict], validation: Optional[dict] = None,
          params: Optional[dict] = None) -> dict:
    """Assemble the whole report for one comparison group."""
    sections = [
        _corpus_overview(view, formula_space, params, exemplars),
        _layers(view, formula_space),
        _core_repertoire(view, formula_space),
        _distinctive(view, formula_space, manuscript_space),
        _attributions(view, formula_space),
        _order(view, manuscript_space, block_list, formula_space),
        _rubrics(rubric_analysis),
        _manuscript_clusters(view, manuscript_space),
        _outliers(view, formula_space, manuscript_space),
        _caveats(view, formula_space, manuscript_space, exemplars, validation, rubric_analysis),
    ]
    return {
        'cohort': view.slug,
        'cohort_label': view.label,
        'sections': [s for s in sections if s],
    }


def _corpus_overview(view, formula_space, params, exemplars=None):
    years = [ms.year_from for ms in view.manuscripts if ms.year_from is not None]
    years += [ms.year_to for ms in view.manuscripts if ms.year_to is not None]
    total_occurrences = sum(len(seq) for seq in view.seqs)
    repeated = sum(
        1 for counts in view.counts for value in counts.values() if value > 1
    )

    # A manuscript that carries essentially a whole tradition is not a codex
    # attesting that tradition; it is the edition the tradition was read off.
    # That is the direct/indirect distinction of textual criticism, and it is the
    # only basis for it this data has - nothing in the catalogue records it.
    indirect = {e['manuscript_uuid'] for e in (exemplars or [])}

    rows = [
        [
            ms.label,
            ms.shelf_mark or '',
            'Indirect' if ms.uuid in indirect else 'Direct',
            len(view.seqs[i]),
            len(view.counts[i]),
            f'{ms.year_from}–{ms.year_to}' if ms.year_from else '',
            round(ms.rubric_coverage, 3),
        ]
        for i, ms in enumerate(view.manuscripts)
    ]
    rows.sort(key=lambda r: -r[3])

    paragraphs = [
        f'This comparison group covers {view.n_manuscripts} manuscripts and '
        f'{view.n_formulas} distinct standardized formulas across '
        f'{total_occurrences} indexed occurrences.',
    ]
    if years:
        paragraphs.append(f'Datable manuscripts span {min(years)}–{max(years)}.')
    if indirect:
        paragraphs.append(
            f'{len(indirect)} of these are marked indirect witnesses: they carry almost the '
            'whole of a recorded tradition, which is the signature of a printed edition or a '
            'reconstruction rather than of a book that happens to contain those prayers. The '
            'rest are direct witnesses — the text is carried by the codex itself. The '
            'distinction is inferred here, not catalogued, and it matters because agreement '
            'between discovered groups and recorded traditions is circular for the indirect '
            'ones; see Method and caveats.'
        )
    if repeated:
        paragraphs.append(
            f'{repeated} formula/manuscript pairs involve repetition — the same prayer '
            'occurring more than once in one book. Repetitions are kept throughout: '
            'which occurrence corresponds to which is part of the evidence, not noise.'
        )

    return _section(
        'overview', 'Corpus overview',
        paragraphs=paragraphs,
        highlights=[
            {'label': 'Manuscripts', 'value': view.n_manuscripts},
            {'label': 'Distinct formulas', 'value': view.n_formulas},
            {'label': 'Occurrences', 'value': total_occurrences},
            {'label': 'Minimum items per manuscript', 'value': (params or {}).get('min_items')},
        ],
        tables=[_table(
            'Manuscripts',
            ['Manuscript', 'Shelf mark', 'Witness', 'Occurrences', 'Distinct formulas',
             'Dated', 'Rubric coverage'],
            rows,
        )],
    )


def _layers(view, formula_space):
    layers = formula_space.layers
    if not layers:
        return _section(
            'layers', 'Liturgical clusters',
            paragraphs=['The comparison group was too small to factor into liturgical clusters.'],
        )

    H = layers['formula_weights']
    W = layers['manuscript_weights']
    k = layers['k']

    shares = normalize_rows(W)

    mixture_rows = [
        [view.manuscripts[i].label] + [round(float(shares[i, l]), 3) for l in range(k)]
        for i in range(view.n_manuscripts)
    ]

    layer_rows = []
    for l in range(k):
        weights = H[l]
        # Distinctiveness keeps a layer's description from being dominated by
        # formulas that simply weigh a lot everywhere.
        share = weights / np.maximum(H.sum(axis=0), 1e-12)
        score = weights * share
        top = np.argsort(score)[::-1][:8]
        labels = [view.formula_meta(int(f)).co_no or view.formula_meta(int(f)).incipit[:40]
                  for f in top]
        dominant = [view.manuscripts[i].label for i in np.argsort(shares[:, l])[::-1][:3]
                    if shares[i, l] > 0.15]
        layer_rows.append([f'Cluster {l + 1}', '; '.join(labels), '; '.join(dominant)])

    return _section(
        'layers', 'Liturgical clusters',
        paragraphs=[
            f'Non-negative matrix factorization resolved the comparison group into {k} liturgical clusters. '
            'Each manuscript is a mixture of them rather than a member of one: this is '
            'the form in which a book can be, say, largely Gregorian while carrying a '
            'Gelasian supplement.',
            'The number of clusters was chosen at the elbow of the reconstruction error curve; '
            'the alternatives are kept in layers.json so the choice can be revisited.',
        ],
        tables=[
            _table('What defines each cluster',
                   ['Cluster', 'Characteristic formulas', 'Dominant manuscripts'], layer_rows),
            _table('Cluster mixture per manuscript',
                   ['Manuscript'] + [f'Cluster {l + 1}' for l in range(k)], mixture_rows),
        ],
    )


def _core_repertoire(view, formula_space):
    df = formula_space.df
    n = view.n_manuscripts

    histogram = [[k, int((df == k).sum())] for k in range(1, n + 1)]

    # Fall back to a lower bar rather than printing an empty table: a comparison group where
    # nothing reaches 80% is itself the finding, and the reader still needs to see
    # what the most widely shared material actually is.
    threshold = max(2, math.ceil(CORE_THRESHOLD * n))
    used_fallback = False
    while threshold > 2 and not (df >= threshold).any():
        threshold -= 1
        used_fallback = True

    core = np.where(df >= threshold)[0]
    order = core[np.argsort(df[core])[::-1]]

    rows = [
        [
            view.formula_meta(int(f)).co_no,
            view.formula_meta(int(f)).incipit,
            int(df[f]),
            int(formula_space.total_counts[f]),
            round(float(formula_space.mean_position[f]), 3),
            round(float(formula_space.position_spread[f]), 3),
        ]
        for f in order
    ]

    shared_at_all = int((df >= 2).sum())
    unique = int((df == 1).sum())

    paragraphs = []
    if used_fallback:
        paragraphs.append(
            f'No formula is present in {math.ceil(CORE_THRESHOLD * n)} of the {n} witnesses '
            f'({int(CORE_THRESHOLD * 100)}% of the comparison group), so there is no core repertoire in '
            'the strict sense. The table falls back to the widest attestation that exists, '
            f'{threshold} witnesses.'
        )
    else:
        paragraphs.append(
            f'{len(core)} formulas appear in at least {threshold} of the {n} witnesses. '
            'These carry almost no discriminating power — precisely why the primary '
            'similarity metric down-weights them — but they define the shared backbone.'
        )

    paragraphs.append(
        f'{unique} formulas ({unique / max(view.n_formulas, 1) * 100:.0f}%) occur in one witness '
        f'only, and {shared_at_all} are shared by two or more. A high share of singletons can '
        'mean genuinely local material, or simply that the witnesses overlap little in what has '
        'been indexed so far.'
    )
    paragraphs.append(
        'Position spread says whether a shared prayer also keeps a shared place: a low value '
        'means the same prayer at the same point in every book.'
    )

    return _section(
        'core', 'Core repertoire — what the witnesses share',
        paragraphs=paragraphs,
        highlights=[
            {'label': 'Formulas at the reported threshold', 'value': int(len(core))},
            {'label': 'Threshold used', 'value': f'{threshold} of {n} witnesses'},
            {'label': 'Shared by ≥2 witnesses', 'value': shared_at_all},
            {'label': 'Unique to one witness', 'value': unique},
        ],
        tables=[
            _table('Most widely attested formulas',
                   ['CO no.', 'Incipit', 'Witnesses', 'Occurrences', 'Mean position',
                    'Position spread'], rows),
            _table('How widely formulas are shared',
                   ['Present in N witnesses', 'Formulas'], histogram),
        ],
    )


def _distinctive(view, formula_space, manuscript_space):
    """Formulas over-represented in one manuscript cluster relative to the rest."""
    k = manuscript_space.suggested_k
    if not k or k not in manuscript_space.cuts:
        return _section(
            'distinctive', 'What separates the groups',
            paragraphs=['No manuscript grouping was stable enough to contrast.'],
        )

    labels = np.asarray(manuscript_space.cuts[k])
    binary = view.incidence_matrix(binary=True)
    tables = []

    for cluster in sorted(set(labels.tolist())):
        inside = labels == cluster
        outside = ~inside
        if not inside.any() or not outside.any():
            continue
        inside_rate = binary[inside].mean(axis=0)
        outside_rate = binary[outside].mean(axis=0)
        lift = inside_rate - outside_rate
        top = np.argsort(lift)[::-1][:20]

        rows = [
            [
                view.formula_meta(int(f)).co_no,
                view.formula_meta(int(f)).incipit,
                round(float(inside_rate[f]), 2),
                round(float(outside_rate[f]), 2),
                round(float(lift[f]), 2),
            ]
            for f in top if lift[f] > 0
        ]
        members = ', '.join(view.manuscripts[i].label for i in np.where(inside)[0])
        tables.append(_table(
            f'Group {cluster}: {members}',
            ['CO no.', 'Incipit', 'Present inside', 'Present outside', 'Difference'],
            rows,
        ))

    return _section(
        'distinctive', 'What separates the groups',
        paragraphs=[
            f'Manuscripts were cut into {k} groups at the best silhouette score. For each '
            'group, the formulas listed are those most over-represented inside it '
            'compared with the rest of the comparison group — the material that makes the group '
            'recognisable.',
            'A difference close to 1.0 means the formula is in every witness of the group '
            'and in none outside it.',
        ],
        tables=tables,
    )


def _attributions(view, formula_space):
    from .formula_space import propose_attributions

    proposals = propose_attributions(formula_space, view)
    labels = formula_space.labels.get('agglomerative')

    unattributed_clusters = []
    if labels is not None:
        from collections import Counter, defaultdict
        known_by_cluster = defaultdict(Counter)
        size = Counter()
        for local, cluster in enumerate(labels):
            if cluster < 0:
                continue
            size[int(cluster)] += 1
            indices = view.corpus.formulas[view.formula_ids[local]].tradition_indices
            for index in indices:
                known_by_cluster[int(cluster)][index] += 1
        for cluster, count in size.most_common():
            if count >= 10 and not known_by_cluster.get(cluster):
                unattributed_clusters.append([cluster, count])

    rows = [
        [p['co_no'], p['incipit'], p['tradition'], p['confidence'], p['cluster_known_members']]
        for p in proposals
    ]

    paragraphs = [
        f'{len(proposals)} formulas carrying no tradition attribution sit inside a cluster '
        'whose already-attributed members belong overwhelmingly to a single tradition. '
        'These are candidates for a scholar to confirm or reject, not conclusions.',
    ]
    if unattributed_clusters:
        paragraphs.append(
            f'{len(unattributed_clusters)} clusters of ten or more formulas contain no '
            'attributed member at all. If such a cluster is liturgically coherent it is a '
            'candidate for a tradition not yet recorded in the database; if it is not, it '
            'more likely reflects a single manuscript\'s local material.'
        )

    return _section(
        'attributions', 'Attribution proposals and candidate traditions',
        paragraphs=paragraphs,
        highlights=[
            {'label': 'Attribution proposals', 'value': len(proposals)},
            {'label': 'Clusters with no attributed member', 'value': len(unattributed_clusters)},
        ],
        tables=[
            _table('Proposed attributions',
                   ['CO no.', 'Incipit', 'Proposed tradition', 'Confidence', 'Cluster evidence'],
                   rows),
            _table('Clusters with no known tradition',
                   ['Cluster', 'Formulas'], unattributed_clusters),
        ],
    )


def _order(view, manuscript_space, block_list, formula_space):
    records = [r for r in manuscript_space.pair_records if r['shared_occurrences'] >= 5]
    rows = [
        [
            view.manuscripts[r['a']].label,
            view.manuscripts[r['b']].label,
            r['shared_occurrences'],
            round(r['nlcs'], 3),
            round(r['kendall_tau_b'], 3),
            round(r['breakpoint_rate'], 3),
            round(r['mean_displacement'], 3),
        ]
        for r in sorted(records, key=lambda r: -r['nlcs'])
    ]

    mobile = np.argsort(formula_space.position_spread)[::-1]
    mobile_rows = [
        [
            view.formula_meta(int(f)).co_no,
            view.formula_meta(int(f)).incipit,
            int(formula_space.df[f]),
            round(float(formula_space.mean_position[f]), 3),
            round(float(formula_space.position_spread[f]), 3),
        ]
        for f in mobile[:60] if formula_space.df[f] >= 3
    ]

    block_rows = [
        [
            b['length'],
            b['support'],
            round(b['mean_position'], 3) if b['mean_position'] is not None else '',
            ' → '.join((f['co_no'] or f['incipit'][:24]) for f in b['formulas'][:8]),
        ]
        for b in block_list[:TABLE_LIMIT]
    ]

    paragraphs = [
        'Order agreement is computed on aligned occurrences, not on deduplicated sets. '
        'NLCS is the share of shared material standing in the same relative order; '
        'breakpoint rate is the share of adjacent prayers that stay adjacent, which is '
        'what identifies a block moving as one piece.',
    ]
    if block_list:
        longest = block_list[0]
        paragraphs.append(
            f'The longest shared run is {longest["length"]} prayers, present in '
            f'{longest["support"]} witnesses.'
        )
    else:
        paragraphs.append(
            'No run of two or more prayers recurs in the required number of witnesses, '
            'which for a small or thinly indexed comparison group is expected.'
        )

    return _section(
        'order', 'Order of prayers',
        paragraphs=paragraphs,
        tables=[
            _table('Pairwise order agreement',
                   ['Manuscript A', 'Manuscript B', 'Shared occurrences', 'NLCS',
                    "Kendall's tau", 'Breakpoint rate', 'Mean displacement'], rows),
            _table('Shared blocks',
                   ['Length', 'Witnesses', 'Mean position', 'Prayers'], block_rows),
            _table('Most mobile material',
                   ['CO no.', 'Incipit', 'Witnesses', 'Mean position', 'Position spread'],
                   mobile_rows,
                   note='High spread means the prayer occupies a different part of the '
                        'book in different witnesses.'),
        ],
    )


def _rubrics(rubric_analysis):
    if not rubric_analysis.get('available'):
        return _section(
            'rubrics', 'Rubric stability',
            paragraphs=[
                rubric_analysis.get('note', 'No rubric data available.'),
                'Once standardized rubrics are recorded, this section reports, for every '
                'prayer, whether it always stands under the same rubric (an anchor) or '
                'moves between rites (a floater) — and the pairwise metrics gain a third '
                'dimension alongside content and order.',
            ],
            highlights=[{'label': 'Rubric coverage', 'value': '0%'}],
        )

    anchors = [
        [r['co_no'], r['incipit'], r['witnesses'], r['modal_rubric']]
        for r in rubric_analysis['anchors']
    ]
    floaters = [
        [r['co_no'], r['incipit'], r['witnesses'], r['distinct_rubrics'],
         r['modal_rubric'], r['modal_share'], r['entropy']]
        for r in rubric_analysis['floaters']
    ]

    return _section(
        'rubrics', 'Rubric stability',
        paragraphs=[
            f'Standardized rubrics cover {rubric_analysis["coverage"] * 100:.1f}% of '
            f'occurrences in this comparison group. Only formulas seen in at least '
            f'{rubric_analysis["min_witnesses"]} witnesses are reported.',
            'Anchors never leave their rubric; floaters are reusable material whose '
            'placement varies, and are usually the more revealing of the two.',
        ],
        highlights=[
            {'label': 'Rubric coverage', 'value': f'{rubric_analysis["coverage"] * 100:.1f}%'},
            {'label': 'Anchors', 'value': len(rubric_analysis['anchors'])},
            {'label': 'Floaters', 'value': len(rubric_analysis['floaters'])},
        ],
        tables=[
            _table('Anchors — always the same rubric',
                   ['CO no.', 'Incipit', 'Witnesses', 'Rubric'], anchors),
            _table('Floaters — rubric varies',
                   ['CO no.', 'Incipit', 'Witnesses', 'Distinct rubrics', 'Modal rubric',
                    'Modal share', 'Entropy'], floaters),
        ],
    )


def _manuscript_clusters(view, manuscript_space):
    k = manuscript_space.suggested_k
    if not k:
        return _section(
            'ms_clusters', 'Manuscript groups',
            paragraphs=['Too few manuscripts to group.'],
        )

    labels = manuscript_space.cuts[k]
    rows = [
        [view.manuscripts[i].label, labels[i]]
        for i in manuscript_space.leaf_order or range(view.n_manuscripts)
    ]
    agreement = manuscript_space.agreement.get(str(k), {})

    paragraphs = [
        f'Average-linkage clustering on idf-weighted content similarity suggests {k} '
        f'groups (best silhouette score '
        f'{manuscript_space.silhouette.get(k, float("nan")):.3f}). Rows are listed in '
        'seriation order — the ordering the dendrogram permits that puts similar '
        'witnesses side by side.',
    ]
    if agreement:
        paragraphs.append(
            f'Against the dominant tradition of each witness, the grouping scores '
            f'ARI {agreement["adjusted_rand_index"]:.3f} and NMI '
            f'{agreement["normalized_mutual_info"]:.3f} over '
            f'{agreement["scored_manuscripts"]} manuscripts. A manuscript has no '
            'tradition of its own in this database — only a mixture inherited from its '
            'formulas — so this compares a grouping against a summary, not against a label.'
        )

    return _section(
        'ms_clusters', 'Manuscript groups',
        paragraphs=paragraphs,
        tables=[_table('Groups in seriation order', ['Manuscript', 'Group'], rows)],
    )


def _outliers(view, formula_space, manuscript_space):
    tables = []
    if manuscript_space.matrices.get('idf_cosine') is not None and view.n_manuscripts > 2:
        similarity = manuscript_space.matrices['idf_cosine'].copy()
        np.fill_diagonal(similarity, np.nan)
        mean_similarity = np.nanmean(similarity, axis=1)
        order = np.argsort(mean_similarity)
        tables.append(_table(
            'Most isolated manuscripts',
            ['Manuscript', 'Mean similarity to the rest', 'Distinct formulas'],
            [[view.manuscripts[i].label, round(float(mean_similarity[i]), 3),
              len(view.counts[i])] for i in order],
        ))

    hdbscan = formula_space.labels.get('hdbscan')
    outlier_count = int((hdbscan < 0).sum()) if hdbscan is not None else 0

    return _section(
        'outliers', 'Outliers',
        paragraphs=[
            f'{outlier_count} formulas were left unassigned by density-based clustering. '
            'These are prayers whose distribution matches no group — either genuinely '
            'idiosyncratic material, or material attested too thinly to place.',
            'An isolated manuscript is not necessarily a liturgical outlier: see the '
            'caveats on indexing completeness.',
        ],
        highlights=[{'label': 'Unassigned formulas', 'value': outlier_count}],
        tables=tables,
    )


def _caveats(view, formula_space, manuscript_space, exemplars, validation, rubric_analysis):
    paragraphs = [
        'Differences between witnesses may reflect how completely each has been indexed '
        'rather than what the books actually contained. A partially indexed manuscript '
        'looks distant from everything on Jaccard similarity while scoring high on '
        'containment; where the two disagree sharply, suspect coverage rather than '
        'liturgy. Occurrence counts per witness are given in the overview for exactly '
        'this reason.',
    ]

    highlights = []
    if exemplars:
        names = '; '.join(
            f'{e["manuscript_label"]} contains {e["coverage"] * 100:.0f}% of "{e["tradition"]}"'
            for e in exemplars
        )
        paragraphs.append(
            'This comparison group contains manuscripts that appear to be the reference editions the '
            f'traditions were defined from ({names}). Any agreement between discovered '
            'clusters and recorded traditions is therefore partly circular: the clustering '
            'rediscovers which edition a prayer was printed in, which is how the '
            'attribution was made in the first place. Agreement scores computed with these '
            'witnesses included should not be read as independent confirmation.'
        )
        highlights.append({'label': 'Indirect witnesses detected', 'value': len(exemplars)})

    if validation:
        if validation.get('performed'):
            paragraphs.append(
                'A held-out pass was run with those witnesses excluded. Reconstructing the '
                f'traditions from the remaining {validation["n_manuscripts"]} manuscripts '
                f'alone gives ARI {validation["adjusted_rand_index"]:.3f} and NMI '
                f'{validation["normalized_mutual_info"]:.3f} '
                f'({validation["comparable_formulas"]} formulas of known tradition). '
                'This is the non-circular figure.'
            )
            highlights.append({
                'label': 'Held-out ARI', 'value': round(validation['adjusted_rand_index'], 3),
            })
        else:
            paragraphs.append(
                'A held-out pass excluding the exemplar witnesses could not be run: '
                f'{validation.get("reason", "not enough remaining evidence")}.'
            )

    if not rubric_analysis.get('available'):
        paragraphs.append(
            'Rubric placement could not be assessed at all, because no content row carries '
            'a standardized rubric. One third of the intended analysis is therefore absent '
            'from this run rather than negative.'
        )

    if view.n_manuscripts < 12:
        paragraphs.append(
            f'With {view.n_manuscripts} witnesses, a formula\'s distribution can take at '
            f'most {2 ** view.n_manuscripts} distinct shapes and silhouette-based choices '
            'of group count are unstable. Treat group boundaries as provisional.'
        )

    paragraphs.append(
        'The 2D and 3D maps are projections for inspection, not measurements: t-SNE '
        'distances between distant points carry no meaning, and cluster sizes on screen '
        'are artefacts of the layout. Read quantities from the matrices and tables.'
    )

    if formula_space.notes or manuscript_space.notes:
        paragraphs.extend(formula_space.notes + manuscript_space.notes)

    return _section('caveats', 'Method and caveats',
                    paragraphs=paragraphs, highlights=highlights)
