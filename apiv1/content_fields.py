"""One declarative description of a Content row for the public API.

Export and import share this table, which is what makes the v1 content format a
true round trip: whatever ``GET .../content/`` hands you can be posted straight
back to ``POST .../content/bulk/``.

The external key names deliberately match the column names the editorial CSV
importer has always used, so spreadsheets already in circulation keep working.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlainField:
    """A scalar column copied verbatim between JSON and the model."""

    key: str
    attr: str
    kind: str = 'text'  # text | int | bool


@dataclass(frozen=True)
class RelationField:
    """A foreign key that may be given as a UUID or as a human-readable name."""

    key: str
    attr: str  # the model attribute, e.g. 'formula_uuid'
    model: str  # indexerapp model name
    lookups: tuple = field(default=())  # name columns tried, in order
    label_fields: tuple = field(default=())  # columns used to render the export label

    @property
    def label_key(self):
        base = self.key[:-3] if self.key.endswith('_id') else self.key
        return f'{base}_label'


PLAIN_FIELDS = (
    PlainField('sequence_in_ms', 'sequence_in_ms', 'int'),
    PlainField('rubric_sequence_in_the_MS', 'rubric_sequence', 'int'),
    PlainField('rubric_name_from_ms', 'rubric_name_from_ms'),
    PlainField('subrubric_name_from_ms', 'subrubric_name_from_ms'),
    PlainField('formula_text_from_ms', 'formula_text'),
    PlainField('where_in_ms_from', 'where_in_ms_from'),
    PlainField('where_in_ms_to', 'where_in_ms_to'),
    PlainField('digital_page_number', 'digital_page_number', 'int'),
    PlainField('original_or_added', 'original_or_added'),
    PlainField('biblical_reference', 'biblical_reference'),
    PlainField('reference_to_other_items', 'reference_to_other_items'),
    PlainField('similarity_by_user', 'similarity_by_user'),
    PlainField('edition_subindex', 'edition_subindex'),
    PlainField('comments', 'comments'),
    PlainField('proper_texts', 'proper_texts', 'bool'),
)

RELATION_FIELDS = (
    RelationField('formula_id', 'formula_uuid', 'Formulas',
                  lookups=(), label_fields=('co_no', 'text')),
    RelationField('rubric_id', 'rubric_uuid', 'RiteNames',
                  lookups=('name',), label_fields=('name',)),
    RelationField('liturgical_genre_id', 'liturgical_genre_uuid', 'LiturgicalGenres',
                  lookups=('title',), label_fields=('title',)),
    RelationField('quire_id', 'quire_uuid', 'Quires',
                  lookups=(), label_fields=('type_of_the_quire',)),
    RelationField('section_id', 'section_uuid', 'Sections',
                  lookups=('name',), label_fields=('name',)),
    RelationField('subsection_id', 'subsection_uuid', 'Sections',
                  lookups=('name',), label_fields=('name',)),
    RelationField('function_id', 'function_uuid', 'ContentFunctions',
                  lookups=('name',), label_fields=('name',)),
    RelationField('subfunction_id', 'subfunction_uuid', 'ContentFunctions',
                  lookups=('name',), label_fields=('name',)),
    # Manuscript-scoped, like quires: one notated stretch of one manuscript. A
    # MusicNotationNames name is accepted too and resolved against the target
    # manuscript's own notation records — see _resolve_music_notation.
    RelationField('music_notation_id', 'music_notation_uuid', 'ManuscriptMusicNotations',
                  lookups=(), label_fields=()),
    RelationField('layer', 'layer_uuid', 'Layer',
                  lookups=('short_name', 'name'), label_fields=('short_name',)),
    RelationField('mass_hour', 'mass_hour_uuid', 'MassHour',
                  lookups=('short_name', 'name'), label_fields=('short_name',)),
    RelationField('genre', 'genre_uuid', 'Genre',
                  lookups=('short_name', 'name'), label_fields=('short_name',)),
    RelationField('season_month', 'season_month_uuid', 'SeasonMonth',
                  lookups=('short_name', 'name'), label_fields=('short_name',)),
    RelationField('week', 'week_uuid', 'Week',
                  lookups=('short_name', 'name'), label_fields=('short_name',)),
    RelationField('day', 'day_uuid', 'Day',
                  lookups=('short_name', 'name'), label_fields=('short_name',)),
    RelationField('text_standarization', 'text_standarization_uuid', 'TextStandarization',
                  lookups=('standard_incipit',), label_fields=('standard_incipit',)),
    RelationField('contributor_id', 'data_contributor_uuid', 'Contributors',
                  lookups=('initials',), label_fields=('initials',)),
    # edition_index is resolved by the composite "<bibliography shortname> c.<sequence>"
    # form the editorial workflow uses, handled separately in importers.py.
    RelationField('edition_index', 'edition_index_uuid', 'EditionContent',
                  lookups=(), label_fields=()),
)

PLAIN_FIELDS_BY_KEY = {spec.key: spec for spec in PLAIN_FIELDS}
RELATION_FIELDS_BY_KEY = {spec.key: spec for spec in RELATION_FIELDS}

ALL_KEYS = frozenset(PLAIN_FIELDS_BY_KEY) | frozenset(RELATION_FIELDS_BY_KEY)

#: Keys accepted on input but not written to the model — quietly tolerated so a
#: payload produced by our own export can be posted back unchanged.
IGNORED_INPUT_KEYS = frozenset(
    {'uuid', 'manuscript_uuid', 'entry_date', 'id'}
    | {spec.label_key for spec in RELATION_FIELDS}
)


# --------------------------------------------------------------------------
# Manuscripts
# --------------------------------------------------------------------------

MANUSCRIPT_PLAIN_FIELDS = (
    PlainField('name', 'name'),
    PlainField('rism_id', 'rism_id'),
    PlainField('foreign_id', 'foreign_id'),
    PlainField('shelf_mark', 'shelf_mark'),
    PlainField('usuarium_shelfmark', 'usuarium_shelfmark'),
    PlainField('common_name', 'common_name'),
    PlainField('liturgical_genre_comment', 'liturgical_genre_comment'),
    PlainField('dating_comment', 'dating_comment'),
    PlainField('place_of_origin_comment', 'place_of_origin_comment'),
    PlainField('how_many_columns_mostly', 'how_many_columns_mostly', 'int'),
    PlainField('lines_per_page_usually', 'lines_per_page_usually', 'int'),
    PlainField('how_many_quires', 'how_many_quires', 'int'),
    PlainField('quires_comment', 'quires_comment'),
    PlainField('foliation_or_pagination', 'foliation_or_pagination'),
    PlainField('decorated', 'decorated', 'bool'),
    PlainField('decoration_comments', 'decoration_comments'),
    PlainField('music_notation', 'music_notation', 'bool'),
    PlainField('music_notation_comments', 'music_notation_comments'),
    PlainField('form_of_an_item', 'form_of_an_item'),
    PlainField('general_comment', 'general_comment'),
    PlainField('links', 'links'),
    PlainField('additional_url', 'additional_url'),
    PlainField('iiif_manifest_url', 'iiif_manifest_url'),
    PlainField('pdf_url', 'pdf_url'),
    PlainField('connected_ms', 'connected_ms'),
    PlainField('where_in_connected_ms', 'where_in_connected_ms'),
    PlainField('display_as_main', 'display_as_main', 'bool'),
)

MANUSCRIPT_RELATION_FIELDS = (
    RelationField('contemporary_repository_place', 'contemporary_repository_place_uuid', 'Places',
                  lookups=('repository_today_local_language', 'repository_today_eng'),
                  label_fields=('repository_today_eng', 'repository_today_local_language')),
    RelationField('dating', 'dating_uuid', 'TimeReference',
                  lookups=('time_description',), label_fields=('time_description',)),
    RelationField('place_of_origin', 'place_of_origin_uuid', 'Places',
                  lookups=('repository_today_eng', 'repository_today_local_language'),
                  label_fields=('repository_today_eng',)),
    RelationField('main_script', 'main_script_uuid', 'ScriptNames',
                  lookups=('name',), label_fields=('name',)),
    RelationField('binding_date', 'binding_date_uuid', 'TimeReference',
                  lookups=('time_description',), label_fields=('time_description',)),
    RelationField('binding_place', 'binding_place_uuid', 'Places',
                  lookups=('repository_today_eng', 'repository_today_local_language'),
                  label_fields=('repository_today_eng',)),
)

MANUSCRIPT_ALL_KEYS = (
    frozenset(spec.key for spec in MANUSCRIPT_PLAIN_FIELDS)
    | frozenset(spec.key for spec in MANUSCRIPT_RELATION_FIELDS)
)

MANUSCRIPT_IGNORED_INPUT_KEYS = frozenset(
    {'uuid', 'id', 'entry_date', 'sync_status', 'content_count'}
    | {spec.label_key for spec in MANUSCRIPT_RELATION_FIELDS}
)
