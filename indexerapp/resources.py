"""
Django Import-Export resources for ETL categories.

This module provides ModelResource classes for all models in main/shared/ms categories,
enabling bulk import/export operations via django-import-export.
"""

from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from indexerapp.models import *


class PlacesResource(resources.ModelResource):
    class Meta:
        model = Places
        exclude = ()


class TimeReferenceResource(resources.ModelResource):
    class Meta:
        model = TimeReference
        exclude = ()


class DecorationTypesResource(resources.ModelResource):
    parent_type = fields.Field(
        column_name='parent_type',
        attribute='parent_type',
        widget=ForeignKeyWidget(DecorationTypes, 'uuid')
    )

    class Meta:
        model = DecorationTypes
        exclude = ()


class ColoursResource(resources.ModelResource):
    parent_colour = fields.Field(
        column_name='parent_colour',
        attribute='parent_colour',
        widget=ForeignKeyWidget(Colours, 'uuid')
    )

    class Meta:
        model = Colours
        exclude = ()


class CalendarResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    rubric_name_standarized = fields.Field(
        column_name='rubric_name_standarized',
        attribute='rubric_name_standarized',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    content = fields.Field(
        column_name='content',
        attribute='content',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    feast_rank = fields.Field(
        column_name='feast_rank',
        attribute='feast_rank',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    date_of_the_addition = fields.Field(
        column_name='date_of_the_addition',
        attribute='date_of_the_addition',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Calendar
        exclude = ()


class DecorationSubjectsResource(resources.ModelResource):
    decoration = fields.Field(
        column_name='decoration',
        attribute='decoration',
        widget=ForeignKeyWidget(Decoration, 'uuid')
    )
    subject = fields.Field(
        column_name='subject',
        attribute='subject',
        widget=ForeignKeyWidget(Subjects, 'uuid')
    )

    class Meta:
        model = DecorationSubjects
        exclude = ()


class DecorationColoursResource(resources.ModelResource):
    decoration = fields.Field(
        column_name='decoration',
        attribute='decoration',
        widget=ForeignKeyWidget(Decoration, 'uuid')
    )
    colour = fields.Field(
        column_name='colour',
        attribute='colour',
        widget=ForeignKeyWidget(Colours, 'uuid')
    )

    class Meta:
        model = DecorationColours
        exclude = ()


class DecorationCharacteristicsResource(resources.ModelResource):
    decoration = fields.Field(
        column_name='decoration',
        attribute='decoration',
        widget=ForeignKeyWidget(Decoration, 'uuid')
    )
    characteristics = fields.Field(
        column_name='characteristics',
        attribute='characteristics',
        widget=ForeignKeyWidget(Characteristics, 'uuid')
    )

    class Meta:
        model = DecorationCharacteristics
        exclude = ()


class DecorationResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    date_of_the_addition = fields.Field(
        column_name='date_of_the_addition',
        attribute='date_of_the_addition',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    content = fields.Field(
        column_name='content',
        attribute='content',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    calendar = fields.Field(
        column_name='calendar',
        attribute='calendar',
        widget=ForeignKeyWidget(Calendar, 'uuid')
    )
    decoration_type = fields.Field(
        column_name='decoration_type',
        attribute='decoration_type',
        widget=ForeignKeyWidget(DecorationTypes, 'uuid')
    )
    decoration_subtype = fields.Field(
        column_name='decoration_subtype',
        attribute='decoration_subtype',
        widget=ForeignKeyWidget(DecorationTypes, 'uuid')
    )
    technique = fields.Field(
        column_name='technique',
        attribute='technique',
        widget=ForeignKeyWidget(DecorationTechniques, 'uuid')
    )
    rubric_name_standarized = fields.Field(
        column_name='rubric_name_standarized',
        attribute='rubric_name_standarized',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Decoration
        exclude = ()


class ManuscriptBibliographyResource(resources.ModelResource):
    bibliography = fields.Field(
        column_name='bibliography',
        attribute='bibliography',
        widget=ForeignKeyWidget(Bibliography, 'uuid')
    )
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )

    class Meta:
        model = ManuscriptBibliography
        exclude = ()


class ConditionResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    conservation_date = fields.Field(
        column_name='conservation_date',
        attribute='conservation_date',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Condition
        exclude = ()


class EditionContentResource(resources.ModelResource):
    bibliography = fields.Field(
        column_name='bibliography',
        attribute='bibliography',
        widget=ForeignKeyWidget(Bibliography, 'uuid')
    )
    formula = fields.Field(
        column_name='formula',
        attribute='formula',
        widget=ForeignKeyWidget(Formulas, 'uuid')
    )
    rubric_name_standarized = fields.Field(
        column_name='rubric_name_standarized',
        attribute='rubric_name_standarized',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    function = fields.Field(
        column_name='function',
        attribute='function',
        widget=ForeignKeyWidget(ContentFunctions, 'uuid')
    )
    subfunction = fields.Field(
        column_name='subfunction',
        attribute='subfunction',
        widget=ForeignKeyWidget(ContentFunctions, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = EditionContent
        exclude = ()


class SectionsResource(resources.ModelResource):
    parent_section = fields.Field(
        column_name='parent_section',
        attribute='parent_section',
        widget=ForeignKeyWidget(Sections, 'uuid')
    )

    class Meta:
        model = Sections
        exclude = ()


class ContentFunctionsResource(resources.ModelResource):
    parent_function = fields.Field(
        column_name='parent_function',
        attribute='parent_function',
        widget=ForeignKeyWidget(ContentFunctions, 'uuid')
    )

    class Meta:
        model = ContentFunctions
        exclude = ()


class ContentResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    formula = fields.Field(
        column_name='formula',
        attribute='formula',
        widget=ForeignKeyWidget(Formulas, 'uuid')
    )
    rubric = fields.Field(
        column_name='rubric',
        attribute='rubric',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    liturgical_genre = fields.Field(
        column_name='liturgical_genre',
        attribute='liturgical_genre',
        widget=ForeignKeyWidget(LiturgicalGenres, 'uuid')
    )
    quire = fields.Field(
        column_name='quire',
        attribute='quire',
        widget=ForeignKeyWidget(Quires, 'uuid')
    )
    section = fields.Field(
        column_name='section',
        attribute='section',
        widget=ForeignKeyWidget(Sections, 'uuid')
    )
    subsection = fields.Field(
        column_name='subsection',
        attribute='subsection',
        widget=ForeignKeyWidget(Sections, 'uuid')
    )
    music_notation = fields.Field(
        column_name='music_notation',
        attribute='music_notation',
        widget=ForeignKeyWidget(ManuscriptMusicNotations, 'uuid')
    )
    function = fields.Field(
        column_name='function',
        attribute='function',
        widget=ForeignKeyWidget(ContentFunctions, 'uuid')
    )
    subfunction = fields.Field(
        column_name='subfunction',
        attribute='subfunction',
        widget=ForeignKeyWidget(ContentFunctions, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )
    edition_index = fields.Field(
        column_name='edition_index',
        attribute='edition_index',
        widget=ForeignKeyWidget(EditionContent, 'uuid')
    )
    text_standarization = fields.Field(
        column_name='text_standarization',
        attribute='text_standarization',
        widget=ForeignKeyWidget(TextStandarization, 'uuid')
    )
    layer = fields.Field(
        column_name='layer',
        attribute='layer',
        widget=ForeignKeyWidget(Layer, 'uuid')
    )
    mass_hour = fields.Field(
        column_name='mass_hour',
        attribute='mass_hour',
        widget=ForeignKeyWidget(MassHour, 'uuid')
    )
    genre = fields.Field(
        column_name='genre',
        attribute='genre',
        widget=ForeignKeyWidget(LiturgicalGenres, 'uuid')
    )
    season_month = fields.Field(
        column_name='season_month',
        attribute='season_month',
        widget=ForeignKeyWidget(SeasonMonth, 'uuid')
    )
    week = fields.Field(
        column_name='week',
        attribute='week',
        widget=ForeignKeyWidget(Week, 'uuid')
    )
    day = fields.Field(
        column_name='day',
        attribute='day',
        widget=ForeignKeyWidget(Day, 'uuid')
    )

    class Meta:
        model = Content
        exclude = ()


class LiturgicalGenresNamesResource(resources.ModelResource):
    genre = fields.Field(
        column_name='genre',
        attribute='genre',
        widget=ForeignKeyWidget(LiturgicalGenres, 'uuid')
    )

    class Meta:
        model = LiturgicalGenresNames
        exclude = ()


class ManuscriptsResource(resources.ModelResource):
    contemporary_repository_place = fields.Field(
        column_name='contemporary_repository_place',
        attribute='contemporary_repository_place',
        widget=ForeignKeyWidget(Places, 'uuid')
    )
    dating = fields.Field(
        column_name='dating',
        attribute='dating',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    place_of_origin = fields.Field(
        column_name='place_of_origin',
        attribute='place_of_origin',
        widget=ForeignKeyWidget(Places, 'uuid')
    )
    main_script = fields.Field(
        column_name='main_script',
        attribute='main_script',
        widget=ForeignKeyWidget(ScriptNames, 'uuid')
    )
    binding_date = fields.Field(
        column_name='binding_date',
        attribute='binding_date',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    binding_place = fields.Field(
        column_name='binding_place',
        attribute='binding_place',
        widget=ForeignKeyWidget(Places, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )
    authors = fields.Field(
        column_name='authors',
        attribute='authors',
        widget=ManyToManyWidget(Contributors, separator=';', field='uuid')
    )

    class Meta:
        model = Manuscripts
        exclude = ('id', 'uuid')  # UUID is auto-generated, id is legacy


class MSProjectsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    project = fields.Field(
        column_name='project',
        attribute='project',
        widget=ForeignKeyWidget(Projects, 'uuid')
    )

    class Meta:
        model = MSProjects
        exclude = ()


class ImageResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )

    class Meta:
        model = Image
        exclude = ()


class CllaResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    dating = fields.Field(
        column_name='dating',
        attribute='dating',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )

    class Meta:
        model = Clla
        exclude = ()


class LayoutsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Layouts
        exclude = ()


class CodicologyResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    parchment_colour = fields.Field(
        column_name='parchment_colour',
        attribute='parchment_colour',
        widget=ForeignKeyWidget(Colours, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Codicology
        exclude = ()


class QuiresResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Quires
        exclude = ()


class WatermarksResource(resources.ModelResource):
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Watermarks
        exclude = ()


class ManuscriptMusicNotationsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    music_notation_name = fields.Field(
        column_name='music_notation_name',
        attribute='music_notation_name',
        widget=ForeignKeyWidget(MusicNotationNames, 'uuid')
    )
    dating = fields.Field(
        column_name='dating',
        attribute='dating',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = ManuscriptMusicNotations
        exclude = ()


class OriginsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    origins_date = fields.Field(
        column_name='origins_date',
        attribute='origins_date',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    origins_place = fields.Field(
        column_name='origins_place',
        attribute='origins_place',
        widget=ForeignKeyWidget(Places, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Origins
        exclude = ()


class ProvenanceResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    date_from = fields.Field(
        column_name='date_from',
        attribute='date_from',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    date_to = fields.Field(
        column_name='date_to',
        attribute='date_to',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    place = fields.Field(
        column_name='place',
        attribute='place',
        widget=ForeignKeyWidget(Places, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Provenance
        exclude = ()


class ManuscriptBindingMaterialsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    material = fields.Field(
        column_name='material',
        attribute='material',
        widget=ForeignKeyWidget(BindingMaterials, 'uuid')
    )

    class Meta:
        model = ManuscriptBindingMaterials
        exclude = ()


class ManuscriptBindingDecorationsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    decoration = fields.Field(
        column_name='decoration',
        attribute='decoration',
        widget=ForeignKeyWidget(BindingDecorationTypes, 'uuid')
    )

    class Meta:
        model = ManuscriptBindingDecorations
        exclude = ()


class ManuscriptBindingComponentsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    component = fields.Field(
        column_name='component',
        attribute='component',
        widget=ForeignKeyWidget(BindingComponents, 'uuid')
    )

    class Meta:
        model = ManuscriptBindingComponents
        exclude = ()


class BindingResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    date = fields.Field(
        column_name='date',
        attribute='date',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    place_of_origin = fields.Field(
        column_name='place_of_origin',
        attribute='place_of_origin',
        widget=ForeignKeyWidget(Places, 'uuid')
    )
    type_of_binding = fields.Field(
        column_name='type_of_binding',
        attribute='type_of_binding',
        widget=ForeignKeyWidget(BindingTypes, 'uuid')
    )
    style_of_binding = fields.Field(
        column_name='style_of_binding',
        attribute='style_of_binding',
        widget=ForeignKeyWidget(BindingStyles, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = Binding
        exclude = ()


class HandsResource(resources.ModelResource):
    dating = fields.Field(
        column_name='dating',
        attribute='dating',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )

    class Meta:
        model = Hands
        exclude = ()


class ManuscriptHandsResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    hand = fields.Field(
        column_name='hand',
        attribute='hand',
        widget=ForeignKeyWidget(Hands, 'uuid')
    )
    script_name = fields.Field(
        column_name='script_name',
        attribute='script_name',
        widget=ForeignKeyWidget(ScriptNames, 'uuid')
    )
    dating = fields.Field(
        column_name='dating',
        attribute='dating',
        widget=ForeignKeyWidget(TimeReference, 'uuid')
    )
    data_contributor = fields.Field(
        column_name='data_contributor',
        attribute='data_contributor',
        widget=ForeignKeyWidget(Contributors, 'uuid')
    )

    class Meta:
        model = ManuscriptHands
        exclude = ()


class ManuscriptWatermarksResource(resources.ModelResource):
    manuscript = fields.Field(
        column_name='manuscript',
        attribute='manuscript',
        widget=ForeignKeyWidget(Manuscripts, 'uuid')
    )
    watermark = fields.Field(
        column_name='watermark',
        attribute='watermark',
        widget=ForeignKeyWidget(Watermarks, 'uuid')
    )

    class Meta:
        model = ManuscriptWatermarks
        exclude = ()


class TraditionsResource(resources.ModelResource):
    genre = fields.Field(
        column_name='genre',
        attribute='genre',
        widget=ForeignKeyWidget(LiturgicalGenres, 'uuid')
    )

    class Meta:
        model = Traditions
        exclude = ()


class RiteNamesResource(resources.ModelResource):
    section = fields.Field(
        column_name='section',
        attribute='section',
        widget=ForeignKeyWidget(Sections, 'uuid')
    )
    ceremony = fields.Field(
        column_name='ceremony',
        attribute='ceremony',
        widget=ForeignKeyWidget(Content, 'uuid')
    )

    class Meta:
        model = RiteNames
        exclude = ()


class MassHourResource(resources.ModelResource):
    type = fields.Field(
        column_name='type',
        attribute='type',
        widget=ForeignKeyWidget(Content, 'uuid')
    )

    class Meta:
        model = MassHour
        exclude = ()


class TopicResource(resources.ModelResource):
    section = fields.Field(
        column_name='section',
        attribute='section',
        widget=ForeignKeyWidget(Sections, 'uuid')
    )
    parent = fields.Field(
        column_name='parent',
        attribute='parent',
        widget=ForeignKeyWidget(Topic, 'uuid')
    )

    class Meta:
        model = Topic
        exclude = ()


class ContentTopicResource(resources.ModelResource):
    content = fields.Field(
        column_name='content',
        attribute='content',
        widget=ForeignKeyWidget(Content, 'uuid')
    )
    topic = fields.Field(
        column_name='topic',
        attribute='topic',
        widget=ForeignKeyWidget(Topic, 'uuid')
    )

    class Meta:
        model = ContentTopic
        exclude = ()


class TextStandarizationResource(resources.ModelResource):
    formula = fields.Field(
        column_name='formula',
        attribute='formula',
        widget=ForeignKeyWidget(Formulas, 'uuid')
    )

    class Meta:
        model = TextStandarization
        exclude = ()


# Registry of resources by category
MAIN_RESOURCES = {
    'places': PlacesResource,
    'timereference': TimeReferenceResource,
}

SHARED_RESOURCES = {
    'decorationtypes': DecorationTypesResource,
    'colours': ColoursResource,
    'calendar': CalendarResource,
    'decorationsubjects': DecorationSubjectsResource,
    'decorationcolours': DecorationColoursResource,
    'decorationcharacteristics': DecorationCharacteristicsResource,
    'decoration': DecorationResource,
    'manuscriptbibliography': ManuscriptBibliographyResource,
    'condition': ConditionResource,
    'editioncontent': EditionContentResource,
    'sections': SectionsResource,
    'contentfunctions': ContentFunctionsResource,
    'content': ContentResource,
    'liturgicalgenresnames': LiturgicalGenresNamesResource,
    'manuscripts': ManuscriptsResource,
    'msprojects': MSProjectsResource,
    'image': ImageResource,
    'clla': CllaResource,
    'layouts': LayoutsResource,
    'codicology': CodicologyResource,
    'quires': QuiresResource,
    'watermarks': WatermarksResource,
    'manuscriptmusicnotations': ManuscriptMusicNotationsResource,
    'origins': OriginsResource,
    'provenance': ProvenanceResource,
    'manuscriptbindingmaterials': ManuscriptBindingMaterialsResource,
    'manuscriptbindingdecorations': ManuscriptBindingDecorationsResource,
    'manuscriptbindingcomponents': ManuscriptBindingComponentsResource,
    'binding': BindingResource,
    'hands': HandsResource,
    'manuscripthands': ManuscriptHandsResource,
    'manuscriptwatermarks': ManuscriptWatermarksResource,
    'traditions': TraditionsResource,
    'ritenames': RiteNamesResource,
    'masshour': MassHourResource,
    'topic': TopicResource,
    'contenttopic': ContentTopicResource,
    'textstandarization': TextStandarizationResource,
}

MS_RESOURCES = {
    'manuscripts': ManuscriptsResource,
    # Add all manuscript-related models here
}