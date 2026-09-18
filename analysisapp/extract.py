"""Corpus extraction: the only module in analysisapp that touches the ORM.

Everything downstream (align, formula_space, ms_space, report) works on the plain
dataclasses defined here, so the analytical code stays testable without a database.

The unit of analysis is the *occurrence* — one `content` row — not the formula.
Repetitions inside a manuscript are signal, never collapsed: a formula appearing
three times in one book is three occurrences at three positions.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from indexerapp.models import (
    Content,
    Formulas,
    LiturgicalGenres,
    ManuscriptGenres,
    Manuscripts,
    RiteNames,
    Traditions,
)

#: How much of a formula's text to keep as a human-readable label.
INCIPIT_CHARS = 160

#: Manuscripts with fewer formula-linked content rows than this are too thin to
#: compare meaningfully; the caller can override it per run.
DEFAULT_MIN_ITEMS = 20


@dataclass
class FormulaMeta:
    """A standardized formula, as a node of the formula space (Stage I)."""

    index: int
    pk: int
    uuid: str
    co_no: str
    incipit: str
    tradition_indices: List[int] = field(default_factory=list)


@dataclass
class TraditionMeta:
    index: int
    pk: int
    uuid: Optional[str]
    name: str
    color_rgb: Optional[str]
    genre_uuid: Optional[str]


@dataclass
class RubricMeta:
    index: int
    uuid: str
    name: str
    english_translation: Optional[str]


@dataclass
class ManuscriptProfile:
    """One manuscript as an ordered sequence of occurrences.

    The four ``*_seq`` lists are parallel and index-aligned: element *i* of each
    describes the *i*-th occurrence in reading order.
    """

    index: int
    pk: int
    uuid: str
    label: str
    shelf_mark: Optional[str]
    common_name: Optional[str]
    genre_uuids: List[str]
    year_from: Optional[int]
    year_to: Optional[int]
    century_from: Optional[int]
    century_to: Optional[int]

    #: Formula index (into Corpus.formulas) for each occurrence, in reading order.
    formula_seq: List[int] = field(default_factory=list)
    #: Normalized position in [0, 1] for each occurrence.
    position_seq: List[float] = field(default_factory=list)
    #: Rubric index (into Corpus.rubrics), or -1 when `content.rubric_uuid` is empty.
    rubric_seq: List[int] = field(default_factory=list)
    #: 0-based ordinal of this occurrence among occurrences of the same formula.
    occ_index_seq: List[int] = field(default_factory=list)

    #: Formula index -> how many times it occurs in this manuscript.
    counts: Dict[int, int] = field(default_factory=dict)
    #: Occurrences whose `sequence_in_ms` was NULL and had to be ordered by pk.
    unordered_items: int = 0

    @property
    def n_items(self) -> int:
        return len(self.formula_seq)

    @property
    def n_distinct(self) -> int:
        return len(self.counts)

    @property
    def rubric_coverage(self) -> float:
        """Share of occurrences carrying a standardized rubric."""
        if not self.rubric_seq:
            return 0.0
        return sum(1 for r in self.rubric_seq if r >= 0) / len(self.rubric_seq)


@dataclass
class Corpus:
    """Everything the pipeline needs, already resolved and index-aligned."""

    manuscripts: List[ManuscriptProfile]
    formulas: List[FormulaMeta]
    traditions: List[TraditionMeta]
    rubrics: List[RubricMeta]
    #: Genre uuid -> display title, for the manuscripts actually present.
    genre_titles: Dict[str, str] = field(default_factory=dict)
    #: Manuscripts dropped for having fewer than `min_items` occurrences.
    skipped_manuscripts: List[dict] = field(default_factory=list)

    @property
    def n_manuscripts(self) -> int:
        return len(self.manuscripts)

    @property
    def n_formulas(self) -> int:
        return len(self.formulas)

    @property
    def rubric_coverage(self) -> float:
        total = sum(ms.n_items for ms in self.manuscripts)
        if not total:
            return 0.0
        covered = sum(sum(1 for r in ms.rubric_seq if r >= 0) for ms in self.manuscripts)
        return covered / total


def resolve_rubric_key(rubric_uuid) -> Optional[str]:
    """Rubric identity used throughout the pipeline.

    Deliberately a single choke point: today it is the standardized
    `content.rubric_uuid` only. When that column gets filled, nothing else needs
    to change; if a raw-text fallback is ever wanted, it belongs here and nowhere
    else.
    """
    if rubric_uuid is None:
        return None
    key = str(rubric_uuid).strip()
    return key or None


def _manuscript_label(name, common_name, shelf_mark) -> str:
    parts = [p for p in (common_name or name, shelf_mark) if p]
    return ' / '.join(parts) if parts else (str(name) if name else 'untitled')


def load_corpus(min_items: int = DEFAULT_MIN_ITEMS,
                manuscript_uuids: Optional[Sequence[str]] = None) -> Corpus:
    """Read the whole comparable corpus in a fixed number of queries.

    `manuscript_uuids` restricts the corpus; `min_items` drops manuscripts too
    thinly indexed to compare. Both end up recorded in the run manifest.
    """
    rows_qs = Content.objects.filter(
        manuscript_uuid__isnull=False,
        formula_uuid__isnull=False,
    )
    if manuscript_uuids:
        rows_qs = rows_qs.filter(manuscript_uuid__in=list(manuscript_uuids))

    # Ordered by pk as a stable tie-breaker so that rows with a NULL
    # `sequence_in_ms` keep their insertion order instead of an arbitrary one.
    rows = list(rows_qs.values_list(
        'manuscript_uuid_id',
        'formula_uuid_id',
        'sequence_in_ms',
        'rubric_uuid_id',
        'liturgical_genre_uuid_id',
        'id',
    ).order_by('id'))

    if not rows:
        return Corpus(manuscripts=[], formulas=[], traditions=[], rubrics=[])

    by_ms = defaultdict(list)
    formula_uuids = set()
    rubric_uuids = set()
    genre_by_ms = defaultdict(lambda: defaultdict(int))

    for ms_uuid, formula_uuid, seq, rubric_uuid, genre_uuid, pk in rows:
        ms_key = str(ms_uuid)
        by_ms[ms_key].append((seq, pk, str(formula_uuid), resolve_rubric_key(rubric_uuid)))
        formula_uuids.add(str(formula_uuid))
        if rubric_uuid is not None:
            rubric_uuids.add(str(rubric_uuid))
        if genre_uuid is not None:
            genre_by_ms[ms_key][str(genre_uuid)] += 1

    formulas, formula_index = _load_formulas(formula_uuids)
    traditions = _load_traditions()
    _attach_traditions(formulas, formula_index, traditions)
    rubrics, rubric_index = _load_rubrics(rubric_uuids)

    manuscripts, skipped = _build_profiles(
        by_ms, formula_index, rubric_index, genre_by_ms, min_items,
    )

    genre_titles = _load_genre_titles(
        {g for ms in manuscripts for g in ms.genre_uuids}
    )

    return Corpus(
        manuscripts=manuscripts,
        formulas=formulas,
        traditions=traditions,
        rubrics=rubrics,
        genre_titles=genre_titles,
        skipped_manuscripts=skipped,
    )


def _load_formulas(formula_uuids):
    records = Formulas.objects.filter(uuid__in=list(formula_uuids)).values_list(
        'id', 'uuid', 'co_no', 'text',
    )
    formulas: List[FormulaMeta] = []
    formula_index: Dict[str, int] = {}
    for pk, uuid, co_no, text in sorted(records, key=lambda r: str(r[1])):
        key = str(uuid)
        incipit = (text or '').strip().replace('\n', ' ')
        if len(incipit) > INCIPIT_CHARS:
            incipit = incipit[:INCIPIT_CHARS].rstrip() + '…'
        formula_index[key] = len(formulas)
        formulas.append(FormulaMeta(
            index=len(formulas),
            pk=pk,
            uuid=key,
            co_no=co_no or '',
            incipit=incipit,
        ))
    return formulas, formula_index


def _load_traditions() -> List[TraditionMeta]:
    records = Traditions.objects.all().values_list(
        'id', 'uuid', 'name', 'color_rgb', 'genre_uuid_id',
    ).order_by('id')
    return [
        TraditionMeta(
            index=i,
            pk=pk,
            uuid=str(uuid) if uuid else None,
            name=name,
            color_rgb=color,
            genre_uuid=str(genre) if genre else None,
        )
        for i, (pk, uuid, name, color, genre) in enumerate(records)
    ]


def _attach_traditions(formulas, formula_index, traditions):
    """Fill FormulaMeta.tradition_indices from the formulas<->traditions M2M.

    The through table links by primary key, not uuid, so we map pk -> index here.
    """
    if not formulas or not traditions:
        return
    tradition_by_pk = {t.pk: t.index for t in traditions}
    formula_by_pk = {f.pk: f.index for f in formulas}

    through = Formulas.tradition.through
    links = through.objects.filter(
        formulas_id__in=list(formula_by_pk.keys()),
    ).values_list('formulas_id', 'traditions_id')

    for formula_pk, tradition_pk in links:
        f_idx = formula_by_pk.get(formula_pk)
        t_idx = tradition_by_pk.get(tradition_pk)
        if f_idx is not None and t_idx is not None:
            formulas[f_idx].tradition_indices.append(t_idx)


def _load_rubrics(rubric_uuids):
    if not rubric_uuids:
        return [], {}
    records = RiteNames.objects.filter(uuid__in=list(rubric_uuids)).values_list(
        'uuid', 'name', 'english_translation',
    )
    rubrics: List[RubricMeta] = []
    rubric_index: Dict[str, int] = {}
    for uuid, name, english in sorted(records, key=lambda r: str(r[0])):
        key = str(uuid)
        rubric_index[key] = len(rubrics)
        rubrics.append(RubricMeta(
            index=len(rubrics),
            uuid=key,
            name=name,
            english_translation=english,
        ))
    return rubrics, rubric_index


def _load_genre_titles(genre_uuids) -> Dict[str, str]:
    if not genre_uuids:
        return {}
    records = LiturgicalGenres.objects.filter(uuid__in=list(genre_uuids)).values_list('uuid', 'title')
    return {str(uuid): title for uuid, title in records}


def _load_manuscript_meta(ms_uuids):
    """Manuscript descriptors plus declared genres, in two queries."""
    records = Manuscripts.objects.filter(uuid__in=list(ms_uuids)).values_list(
        'id', 'uuid', 'name', 'common_name', 'shelf_mark',
        'dating_uuid__year_from', 'dating_uuid__year_to',
        'dating_uuid__century_from', 'dating_uuid__century_to',
    )
    meta = {}
    for (pk, uuid, name, common_name, shelf_mark,
         year_from, year_to, century_from, century_to) in records:
        meta[str(uuid)] = {
            'pk': pk,
            'label': _manuscript_label(name, common_name, shelf_mark),
            'shelf_mark': shelf_mark,
            'common_name': common_name,
            'year_from': year_from,
            'year_to': year_to,
            'century_from': century_from,
            'century_to': century_to,
        }

    declared_genres = defaultdict(list)
    genre_links = ManuscriptGenres.objects.filter(
        manuscript_uuid__in=list(ms_uuids), genre_uuid__isnull=False,
    ).values_list('manuscript_uuid_id', 'genre_uuid_id')
    for ms_uuid, genre_uuid in genre_links:
        declared_genres[str(ms_uuid)].append(str(genre_uuid))

    return meta, declared_genres


def _build_profiles(by_ms, formula_index, rubric_index, genre_by_ms, min_items):
    meta, declared_genres = _load_manuscript_meta(by_ms.keys())

    profiles: List[ManuscriptProfile] = []
    skipped: List[dict] = []

    for ms_uuid in sorted(by_ms.keys()):
        entries = by_ms[ms_uuid]
        ms_meta = meta.get(ms_uuid)
        if ms_meta is None:
            # Content pointing at a manuscript that no longer exists.
            skipped.append({'uuid': ms_uuid, 'reason': 'manuscript_missing', 'n_items': len(entries)})
            continue
        if len(entries) < min_items:
            skipped.append({
                'uuid': ms_uuid,
                'label': ms_meta['label'],
                'reason': 'below_min_items',
                'n_items': len(entries),
            })
            continue

        # NULL `sequence_in_ms` sorts last and keeps insertion order among itself,
        # so a partially sequenced manuscript degrades instead of scrambling.
        ordered = sorted(entries, key=lambda e: (e[0] is None, e[0] if e[0] is not None else 0, e[1]))
        unordered_items = sum(1 for e in entries if e[0] is None)

        profile = ManuscriptProfile(
            index=len(profiles),
            pk=ms_meta['pk'],
            uuid=ms_uuid,
            label=ms_meta['label'],
            shelf_mark=ms_meta['shelf_mark'],
            common_name=ms_meta['common_name'],
            genre_uuids=_resolve_genres(ms_uuid, declared_genres, genre_by_ms),
            year_from=ms_meta['year_from'],
            year_to=ms_meta['year_to'],
            century_from=ms_meta['century_from'],
            century_to=ms_meta['century_to'],
            unordered_items=unordered_items,
        )

        total = len(ordered)
        denominator = max(total - 1, 1)
        seen = defaultdict(int)
        for i, (_seq, _pk, formula_uuid, rubric_key) in enumerate(ordered):
            f_idx = formula_index[formula_uuid]
            profile.formula_seq.append(f_idx)
            profile.position_seq.append(i / denominator)
            profile.rubric_seq.append(rubric_index.get(rubric_key, -1) if rubric_key else -1)
            profile.occ_index_seq.append(seen[f_idx])
            seen[f_idx] += 1
        profile.counts = dict(seen)

        profiles.append(profile)

    # `index` must match the position in the final list for every downstream lookup.
    for i, profile in enumerate(profiles):
        profile.index = i

    return profiles, skipped


def _resolve_genres(ms_uuid, declared_genres, genre_by_ms) -> List[str]:
    """Genres a manuscript belongs to, for cohort assignment.

    Prefers what the cataloguer declared in `manuscript_genres`; falls back to the
    genre most often recorded on the manuscript's own content rows.
    """
    declared = declared_genres.get(ms_uuid)
    if declared:
        return sorted(set(declared))
    observed = genre_by_ms.get(ms_uuid)
    if observed:
        modal = max(observed.items(), key=lambda kv: (kv[1], kv[0]))[0]
        return [modal]
    return []


def build_cohorts(corpus: Corpus, min_manuscripts: int = 2):
    """Split the corpus into per-genre cohorts plus one global cohort.

    A manuscript catalogued under several genres takes part in each of them.
    Returns a list of ``(slug, label, [manuscript indices])``.
    """
    from .models import GLOBAL_COHORT_SLUG

    cohorts = []
    all_indices = [ms.index for ms in corpus.manuscripts]
    if len(all_indices) >= min_manuscripts:
        cohorts.append((GLOBAL_COHORT_SLUG, 'All manuscripts', all_indices))

    by_genre = defaultdict(list)
    for ms in corpus.manuscripts:
        for genre_uuid in ms.genre_uuids:
            by_genre[genre_uuid].append(ms.index)

    for genre_uuid in sorted(by_genre, key=lambda g: corpus.genre_titles.get(g, g)):
        indices = by_genre[genre_uuid]
        if len(indices) < min_manuscripts:
            continue
        label = corpus.genre_titles.get(genre_uuid, genre_uuid)
        cohorts.append((f'genre-{genre_uuid}', label, indices))

    return cohorts


def summarize_manuscripts() -> dict:
    """Every manuscript that could take part in a run, with the genres it falls under.

    This is what the manuscript picker is drawn from, so it must agree with what a
    run would actually do: the same eligibility rule (content rows carrying a
    standardized formula), and the same genre resolution as `_resolve_genres`, so
    that ticking a genre selects exactly the manuscripts that genre's cohort would
    contain.

    Counting is done in the database rather than by loading the corpus — the
    picker needs five numbers per manuscript, not every occurrence in the
    catalogue. `min_items` is deliberately not applied here: the caller is choosing
    a threshold at the same time as a selection, so it needs to see the manuscripts
    that threshold would exclude, not have them silently withheld.
    """
    from django.db.models import Count

    rows = list(
        Content.objects
        .filter(manuscript_uuid__isnull=False, formula_uuid__isnull=False)
        .values('manuscript_uuid')
        .annotate(
            n_items=Count('id'),
            n_distinct=Count('formula_uuid', distinct=True),
        )
    )
    counts = {str(row['manuscript_uuid']): row for row in rows}
    if not counts:
        return {'manuscripts': [], 'genres': []}

    observed = defaultdict(lambda: defaultdict(int))
    for row in (
        Content.objects
        .filter(manuscript_uuid__in=list(counts.keys()),
                formula_uuid__isnull=False,
                liturgical_genre_uuid__isnull=False)
        .values('manuscript_uuid', 'liturgical_genre_uuid')
        .annotate(n=Count('id'))
    ):
        observed[str(row['manuscript_uuid'])][str(row['liturgical_genre_uuid'])] = row['n']

    meta, declared_genres = _load_manuscript_meta(counts.keys())

    manuscripts = []
    genre_usage = defaultdict(int)
    for ms_uuid in sorted(counts.keys()):
        ms_meta = meta.get(ms_uuid)
        if ms_meta is None:
            # Content pointing at a manuscript that no longer exists.
            continue
        genres = _resolve_genres(ms_uuid, declared_genres, observed)
        for genre_uuid in genres:
            genre_usage[genre_uuid] += 1
        manuscripts.append({
            'uuid': ms_uuid,
            'label': ms_meta['label'],
            'shelf_mark': ms_meta['shelf_mark'] or '',
            'n_items': counts[ms_uuid]['n_items'],
            'n_distinct': counts[ms_uuid]['n_distinct'],
            'year_from': ms_meta['year_from'],
            'year_to': ms_meta['year_to'],
            'genres': genres,
        })

    manuscripts.sort(key=lambda m: m['label'].lower())

    titles = _load_genre_titles(genre_usage.keys())
    genres = [
        {'uuid': uuid, 'title': titles.get(uuid, uuid), 'manuscripts': count}
        for uuid, count in genre_usage.items()
    ]
    genres.sort(key=lambda g: g['title'].lower())

    return {'manuscripts': manuscripts, 'genres': genres}
