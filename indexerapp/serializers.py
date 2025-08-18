from rest_framework import serializers
from decimal import Decimal
from collections import OrderedDict

from .models import RiteNames, Provenance, Content, Manuscripts, Contributors, Quires, ManuscriptHands, Hands, ScriptNames, Places, TimeReference, Sections, ContentFunctions, ManuscriptMusicNotations, EditionContent

class RiteNamesSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiteNames
        fields = (
            'id', 'name'
        )

class ContributorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributors
        fields = (
            'id', 'initials', 'first_name', 'last_name'
        )
        
    def to_representation(self, instance):
        return f"{instance.first_name[0].upper()}.{instance.last_name[0].upper()}."

class ScriptNamesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptNames
        fields = ['name']

class HandsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hands
        fields = ['name']

class PlacesSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Places
        fields = ['name', 'latitude', 'longitude']

class PlacesSerializerNoCountry(serializers.ModelSerializer):
    class Meta:
        model = Places
        fields = (
            'city_today_eng', 'repository_today_eng',
        )
        
    def to_representation(self, instance):
        return f"{instance.city_today_eng}, {instance.repository_today_eng}."

class PlacesSerializerOnlyCountry(serializers.ModelSerializer):
    class Meta:
        model = Places
        fields = (
            'country_today_eng',
        )
        
    def to_representation(self, instance):
        return f"{instance.country_today_eng}."

class TimeReferenceSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = TimeReference
        fields = ['name']

class SectionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sections
        fields = '__all__'

class ContentFunctionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentFunctions
        fields = '__all__'

class ManuscriptMusicNotationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManuscriptMusicNotations
        fields = '__all__'

class EditionContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EditionContent
        fields = '__all__'

class QuiresSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quires
        fields = '__all__'

class ProvenanceSerializer(serializers.ModelSerializer):
    place = PlacesSerializer()

    class Meta:
        model = Provenance
        fields = ('date_from', 'date_to', 'place', 'timeline_sequence')
    
    def to_representation(self, instance):
        place_rep = self.fields['place'].to_representation(instance.place)
        date_from = instance.date_from.time_description if instance.date_from else "?"
        date_to = instance.date_to.time_description if instance.date_to else "?"
        return f"{place_rep['name']} ({date_from} - {date_to})"

class ManuscriptsSerializer(serializers.ModelSerializer):
    dating = TimeReferenceSerializer()
    main_script = ScriptNamesSerializer()
    binding_date = TimeReferenceSerializer()
    contemporary_repository_place_name = serializers.CharField(source='contemporary_repository_place.__str__', allow_null=True, read_only=True)
    contemporary_repository_place_latitude = serializers.FloatField(source='contemporary_repository_place.latitude', allow_null=True, read_only=True)
    contemporary_repository_place_longitude = serializers.FloatField(source='contemporary_repository_place.longitude', allow_null=True, read_only=True)
    place_of_origin_name = serializers.CharField(source='place_of_origin.__str__', allow_null=True, read_only=True)
    place_of_origin_latitude = serializers.FloatField(source='place_of_origin.latitude', allow_null=True, read_only=True)
    place_of_origin_longitude = serializers.FloatField(source='place_of_origin.longitude', allow_null=True, read_only=True)
    binding_place_name = serializers.CharField(source='binding_place.__str__', allow_null=True, read_only=True)
    binding_place_latitude = serializers.FloatField(source='binding_place.latitude', allow_null=True, read_only=True)
    binding_place_longitude = serializers.FloatField(source='binding_place.longitude', allow_null=True, read_only=True)

    class Meta:
        model = Manuscripts
        fields = (
            'id',
            'name',
            'foreign_id',
            'rism_id',
            'image',
            'contemporary_repository_place',
            'shelf_mark',
            'dating',
            'place_of_origin',
            'main_script',
            'how_many_columns_mostly',
            'lines_per_page_usually',
            'how_many_quires',
            'foliation_or_pagination',
            'decorated',
            'music_notation',
            'binding_date',
            'binding_place',
            'ms_provenance',
            'contemporary_repository_place_name',
            'contemporary_repository_place_latitude',
            'contemporary_repository_place_longitude',
            'place_of_origin_name',
            'place_of_origin_latitude',
            'place_of_origin_longitude',
            'binding_place_name',
            'binding_place_latitude',
            'binding_place_longitude',
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['dating'] = str(instance.dating)
        representation['main_script'] = str(instance.main_script)
        representation['binding_date'] = str(instance.binding_date)

        representation['dating_year'] = 9999
        if instance.dating:
            representation['dating_year'] = str(instance.dating.year_from)

        provenances = instance.ms_provenance.all().order_by('timeline_sequence')
        representation['ms_provenance'] = ''
        if len(provenances) > 0:
            ms_provenance = OrderedDict()
            for p in provenances:
                if p.date_from and p.date_from.year_to <= 1501 and p.place:
                    if p.place.repository_today_eng:
                        ms_provenance[p.place.repository_today_eng] = None
                    elif p.place.city_today_eng:
                        ms_provenance[p.place.city_today_eng] = None
                    elif p.place.region_today_eng:
                        ms_provenance[p.place.region_today_eng] = None
                    elif p.place.country_historic_eng:
                        ms_provenance[p.place.country_historic_eng] = None
            representation['ms_provenance'] = ' - '.join(ms_provenance.keys())

        representation['page_size_max_h'] = '-'
        representation['page_size_max_w'] = '-'
        codicology = instance.ms_codicology.all()
        representation['folios_no'] = 0
        if len(codicology) > 0:
            if codicology[0].number_of_paper_leaves:
                representation['folios_no'] += codicology[0].number_of_paper_leaves
            if codicology[0].number_of_parchment_folios:
                representation['folios_no'] += codicology[0].number_of_parchment_folios
            representation['page_size_max_h'] = codicology[0].page_size_max_height
            representation['page_size_max_w'] = codicology[0].page_size_max_width

        if not representation['folios_no']:
            representation['folios_no'] = '-'

        return representation

class ManuscriptHandsSerializer(serializers.ModelSerializer):
    manuscript = ManuscriptsSerializer()
    hand = HandsSerializer()
    script_name = ScriptNamesSerializer()
    authors = ContributorsSerializer(many=True)
    data_contributor = ContributorsSerializer()

    class Meta:
        model = ManuscriptHands
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['manuscript'] = str(instance.manuscript)
        representation['hand'] = str(instance.hand)
        representation['script_name'] = str(instance.script_name)
        representation['authors'] = ", ".join(
            [str(contributor) for contributor in instance.authors.all()]
        )
        representation['data_contributor'] = str(instance.data_contributor)
        return representation

class ContentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    manuscript_name = serializers.SerializerMethodField()
    rite = RiteNamesSerializer
    formula_standarized = serializers.SerializerMethodField()
    data_contributor = ContributorsSerializer
    authors = ContributorsSerializer(many=True)
    similarity_levenshtein_percent = serializers.DecimalField(max_digits=5, decimal_places=1) 
    
    section = SectionsSerializer
    subsection = SectionsSerializer
    function = ContentFunctionsSerializer
    subfunction = ContentFunctionsSerializer
    quire = QuiresSerializer
    music_notation = ManuscriptMusicNotationsSerializer
    edition_index = EditionContentSerializer

    traditions = serializers.SerializerMethodField()

    translation = serializers.SerializerMethodField()

    class Meta:
        model = Content
        fields = (
            'id', 'manuscript', 'quire', 'manuscript_name', 'section', 'subsection', 'function', 'subfunction', 'biblical_reference', 'formula', 'traditions', 'formula_standarized', 'music_notation', 'rite', 'rite_name_from_ms', 'formula_text', 'sequence_in_ms', 'where_in_ms_from', 'where_in_ms_to', 'similarity_by_user', 'similarity_levenshtein', 'similarity_levenshtein_percent', 'original_or_added', 'reference_to_other_items', 'subrite_name_from_ms', 'edition_index', 'edition_subindex', 'data_contributor', 'authors', 'proper_texts', 'translation', 
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['authors'] = ", ".join(
            [str(contributor) for contributor in instance.authors.all()]
        )
        representation['data_contributor'] = str(instance.data_contributor)
        representation['section'] = str(instance.section)
        representation['subsection'] = str(instance.subsection)
        representation['function'] = str(instance.function)
        representation['subfunction'] = str(instance.subfunction)
        representation['quire'] = str(instance.quire)
        representation['music_notation'] = str(instance.music_notation)
        representation['edition_index'] = str(instance.edition_index)
        return representation

    def get_liturgical_genre(self, content):
        return ', '.join([str(genre) for content in content.content_genres.all()])

    def get_traditions(self, content):
        if content.formula:
            return ', '.join([str(tradition) for tradition in content.formula.tradition.all()])
        return ''

    def get_manuscript_name(self, content):
        return content.manuscript.name

    def get_formula_standarized(self, content):
        if content.formula:
            return content.formula.text
        return ''

    def get_translation(self, content):
        if content.formula:
            return content.formula.translation
        return ''

    def get_data_contributor(self, content):
        return content.data_contributor.initials