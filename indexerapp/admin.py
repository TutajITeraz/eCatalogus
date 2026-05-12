from django.contrib import admin
from django.contrib.admin.options import BaseModelAdmin
from .models import *
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper

from django.db import models
from django.forms import TextInput, Textarea
from django.core.exceptions import ValidationError
from admin_searchable_dropdown.filters import AutocompleteFilter
from import_export.admin import ImportExportModelAdmin
from .resources import *
#from zotero.admin import TagInlineAdmin

from django import forms

from django.template.defaultfilters import linebreaksbr

#for add debate:
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.utils import quote
 

class UUIDAutocompleteResultMixin:
    def get_result_value(self, item):
        item_uuid = getattr(item, 'uuid', None)
        if item_uuid:
            return str(item_uuid)
        return str(getattr(item, 'pk', item))
from django.contrib.admin.views.main import ChangeList
from django.urls import reverse
from django.utils.html import format_html
from django.templatetags.static import static

from decimal import Decimal
import math
import uuid
from types import MethodType

import modelclone

#For filters:
from django.db.models import Q


from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User


UUID_LOOKUP_EXEMPT_MODELS = set()


def _model_prefers_uuid_lookup(model):
    if model in UUID_LOOKUP_EXEMPT_MODELS:
        return False

    try:
        model._meta.get_field('uuid')
    except Exception:
        return False

    return True




########################  FolioPaginationWidget  ###################################

from django.utils.safestring import mark_safe




class FolioPaginationWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = (TextInput(attrs={'pattern': r'^\d+(\.\d+)?[rv]?$'}),)
        super().__init__(widgets, attrs)

    def decompress(self, value):
        print('decompress ',value)
        if value is not None:
            value_str = str(value)
            if value_str.endswith('.1'):
                return [(value_str.replace('.1','r'))]
            elif value_str.endswith('.2'):
                return [(value_str.replace('.2','v'))]
            else:
                return [str(value)]
        return [None]


class FolioPaginationField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        # kwargs może zawierać required, label, help_text itp.
        fields = (
            forms.DecimalField(
                max_digits=5, 
                decimal_places=1, 
                widget=TextInput(attrs={'pattern': r'^\d+(\.\d+)?[rv]?$'})
            ),
        )
        # require_all_fields=False można zostawić lub przepuścić z kwargs
        kwargs.setdefault('require_all_fields', False)

        super().__init__(fields, *args, **kwargs)

    def to_python(self, value):
        print('to_python ',value)
        if value:
            if value.endswith('r'):
                return Decimal(value[:-1]) + Decimal('0.1')
            elif value.endswith('v'):
                return Decimal(value[:-1]) + Decimal('0.2')
            else:
                return Decimal(value)
        return None

def clean(self, value):
    # value może być None lub pustą listą
    if not value or not value[0]:
        return None
    return self.to_python(value[0])
##############################################################


#DO I Need it? 
from dal import autocomplete

#TODO [ ]TODO nigdzie nie użyte
class FormulasForm(forms.ModelForm):
    class Meta:
        model = Formulas
        fields = ('__all__')
        widgets = {
            'text': autocomplete.ModelSelect2(url='formula-autocomplete', attrs={'style': 'width: 200px;'})
        }
        #ModelSelect2 gdy nie ma url ;)

class ContentForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField(required=False)

    class Meta:
        model = Content
        fields = ('__all__')
        widgets = {
            'formula_uuid': autocomplete.ListSelect2(url='formula-autocomplete', attrs={'style': 'width: 400px;'}),
            'rite': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 400px;'}),
            'genre_uuid': autocomplete.ListSelect2(url='genre-autocomplete', attrs={'style': 'width: 400px;'})
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subjects
        fields = ('__all__')
        widgets = {
            'name': autocomplete.ModelSelect2(url='subject-autocomplete', attrs={'style': 'width: 200px;'})
        }
        #ModelSelect2 gdy nie ma url ;)

class DecorationSubjectsForm(forms.ModelForm):
    class Meta:
        model = Subjects
        fields = ('__all__')
        widgets = {
            'subject': autocomplete.ModelSelect2(url='subject-autocomplete', attrs={'style': 'width: 200px;'})
        }

class DecorationColoursForm(forms.ModelForm):
    class Meta:
        model = Colours
        fields = ('__all__')
        widgets = {
            'colour': autocomplete.ModelSelect2(url='colours-autocomplete', attrs={'style': 'width: 200px;'})
        }

class DecorationCharacteristicsForm(forms.ModelForm):
    class Meta:
        model = Characteristics
        fields = ('__all__')
        widgets = {
            'colour': autocomplete.ModelSelect2(url='characteristics-autocomplete', attrs={'style': 'width: 200px;'})
        }

class EditionContentForm(forms.ModelForm):
    class Meta:
        model = EditionContent
        fields = ('__all__')
        widgets = {
            'rubric_name_standarized_uuid': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 200px;'})
        }


### INLINES ###
"""
class RitesInline(admin.TabularInline):
    model = Rites

    show_change_link=True
    form = autocomplete.FutureModelForm

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }
"""
class ContentInline(admin.TabularInline):
    model = Content
    fk_name = 'manuscript_uuid'

    form = autocomplete.FutureModelForm
    show_change_link=True

    form = ContentForm #It works!

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class FormulasInline(admin.TabularInline):
    model = Formulas

    form = FormulasForm

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

# New inlines
class DecorationSubjectsInline(admin.StackedInline):
    model = DecorationSubjects
    fk_name = 'decoration_uuid'
    extra = 0

    form = DecorationSubjectsForm

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

# New inlines
class DecorationColoursInline(admin.StackedInline):
    model = DecorationColours
    fk_name = 'decoration_uuid'
    extra = 0

    form = DecorationColoursForm

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

# New inlines
class DecorationCharacteristicsInline(admin.StackedInline):
    model = DecorationCharacteristics
    fk_name = 'decoration_uuid'
    extra = 0

    form = DecorationCharacteristicsForm

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }


class ManuscriptBibliographyInline(admin.TabularInline):
    model = ManuscriptBibliography
    fk_name = 'manuscript_uuid'
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class OriginsInline(admin.TabularInline):
    model = Origins
    fk_name = 'manuscript_uuid'
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class ProvenanceInline(admin.TabularInline):
    model = Provenance
    fk_name = 'manuscript_uuid'
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class ManuscriptBindingMaterialsInline(admin.TabularInline):
    model = ManuscriptBindingMaterials
    fk_name = 'manuscript_uuid'
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class ManuscriptBindingComponentsInline(admin.TabularInline):
    model = ManuscriptBindingComponents
    fk_name = 'manuscript_uuid'
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

    

class ManuscriptGenresInline(admin.TabularInline):
    model = ManuscriptGenres
    fk_name = 'manuscript_uuid'
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }


# Formulas filters
class FormulasFilter(AutocompleteFilter):
    title = "Formulas"
    field_name = 'formula_uuid'
    field_pk = 'uuid'

class FormulaAutocomplete(UUIDAutocompleteResultMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Formulas.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


# Manuscripts filters
class ManuscriptsFilter(AutocompleteFilter):
    title = "Manuscripts"
    field_name = 'manuscript_uuid'
    field_pk = 'uuid'

class ManuscriptsAutocomplete(UUIDAutocompleteResultMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Manuscripts.objects.all()

        if self.q:
            qs = qs.filter(
                Q(name__istartswith=self.q) |
                Q(shelf_mark__istartswith=self.q) |
                Q(foreign_id__istartswith=self.q) |
                Q(common_name__istartswith=self.q) |
                Q(rism_id__istartswith=self.q)
            )

        return qs

# Register your models here.




class CustomDebateableAdmin(modelclone.ClonableModelAdmin):
    def get_form(self, request, obj=None, **kwargs):
        if obj != None:
            self.obj = obj
        return super().get_form(request, obj, **kwargs)

    def get_debate(self, obj, db_field_name):
        content_type = ContentType.objects.get_for_model(obj)
        debates = AttributeDebate.for_instance(obj).filter(
            content_type=content_type,
            field_name=db_field_name,
        )

        debates_links = [
            f'<a href="#" style="cursor: pointer;" onclick="window.open(\'{self._get_debate_admin_url(debate, "change")}?_popup=1\', \'DebatePopup\', \'height=500,width=800,resizable=yes,scrollbars=yes\'); return false;">{debate.text}</a> '
            f'<a href="#" style="color: red; cursor: pointer;" onclick="window.open(\'{self._get_debate_admin_url(debate, "delete")}?_popup=1\', \'DebateDeletePopup\', \'height=500,width=800,resizable=yes,scrollbars=yes\'); return false;">⌫</a>'
            for debate in debates
        ]
        return debates_links

    def _get_debate_admin_url(self, debate, action):
        lookup_value = getattr(debate, 'uuid', None) if _model_prefers_uuid_lookup(AttributeDebate) else None
        if not lookup_value:
            lookup_value = debate.pk

        return reverse(f'admin:indexerapp_attributedebate_{action}', args=(quote(lookup_value),))


    def add_debate_link(self, obj, db_field, field):
        debate_add_url = reverse("admin:indexerapp_attributedebate_add")
        content_type = ContentType.objects.get_for_model(obj)
        object_uuid = getattr(obj, 'uuid', None) if obj else None
        debate_add_url_with_parameters = f"{debate_add_url}?_popup=1&content_type={content_type.id}&field_name={db_field.name}"
        if object_uuid:
            debate_add_url_with_parameters += f"&object_uuid={object_uuid}"

        return f'<a href="{debate_add_url_with_parameters}" class="add-debate" onclick="return showAddAnotherPopup(this);">💬 Debate</a>'


    def formfield_for_dbfield(self, db_field, **kwargs):
        # pobierz oryginalne pole formularza od Django (może zwrócić None!)
        field = super().formfield_for_dbfield(db_field, **kwargs)

        if field is not None:
            # jeśli pole w modelu ma blank=True → wymuś required=False w formularzu
            if getattr(db_field, "blank", False):
                field.required = False

            if db_field.name not in ['id', 'created_at', 'updated_at']:
                if hasattr(self, 'obj') and self.obj:
                    debates = self.get_debate(self.obj, db_field.name)
                    field.help_text = ', '.join(debates)
                    field.help_text += ' ' + self.add_debate_link(self.obj, db_field, field)
                #else:
                    #field.help_text += ' ' + self.add_debate_link(None, db_field, field)

        #if db_field.name in ['folio_starting', ]:
        #    field = FolioPaginationField

        return field

    
    # def where_in_ms_start(self, obj):
    #     # Custom formatting logic
    #     value = obj.where_in_ms_from
    #     if value is not None:
    #         formatted_value = str(value).replace('.2', 'v').replace('.1', 'r').replace('.0', '')
    #         return formatted_value
    #     return None

    # def where_in_ms_end(self, obj):
    #     # Custom formatting logic
    #     value = obj.where_in_ms_to
    #     if value is not None:
    #         formatted_value = str(value).replace('.2', 'v').replace('.1', 'r').replace('.0', '')
    #         return formatted_value
    #     return None

    # where_in_ms_start.short_description = 'where in ms from'
    # where_in_ms_end.short_description = 'where in ms to'


class ImportExportDebateableAdmin(CustomDebateableAdmin, ImportExportModelAdmin):
    """
    Combined admin class that inherits from both CustomDebateableAdmin and ImportExportModelAdmin
    to provide debate functionality and import/export capabilities.
    """
    pass


class EditionContentAdmin(ImportExportDebateableAdmin):
    resource_class = EditionContentResource
    form = EditionContentForm

    list_display=  ['id','short_name']+[field.name for field in EditionContent._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    list_filter = [FormulasFilter]
    autocomplete_fields = [
        'bibliography_uuid',
        'formula_uuid',
        'rubric_name_standarized_uuid',
        'function_uuid',
        'subfunction_uuid',
        'data_contributor_uuid',
    ]
    search_fields = [
        'bibliography_uuid__title__icontains',
        'formula_uuid__text__icontains',
        'page',
    ]


    def formula_standarized(self,obj):
        if obj.formula is not None:
            return linebreaksbr(obj.formula.text)
        return ''
    
    def short_name(self,obj):
        return str(obj)

# @admin.register(Content)
class ContentAdmin(ImportExportDebateableAdmin):
    form = ContentForm
    list_display= ['id', 'manuscript', 'formula_text', 'formula_standarized', 'rubric_name_from_ms', 'similarity_levenshtein', 'where_in_ms_from', 'where_in_ms_to', 'original_or_added', 'biblical_reference', 'reference_to_other_items', 'similarity_by_user', 'entry_date', 'sequence_in_ms', 'edition_index', 'comments']


    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]


    #wrapped_field= easy.SimpleAdminField(lambda x: linebreaksbr(x.formula), 'formula', 'formula')

    list_filter = [FormulasFilter, ManuscriptsFilter]
    autocomplete_fields = [
        'manuscript_uuid',
        'formula_uuid',
        'rubric_uuid',
        'liturgical_genre_uuid',
        'quire_uuid',
        'section_uuid',
        'subsection_uuid',
        'function_uuid',
        'subfunction_uuid',
        'data_contributor_uuid',
        'edition_index_uuid',
        'genre_uuid',
        'season_month_uuid',
        'week_uuid',
        'day_uuid',
        'mass_hour_uuid',
        'layer_uuid',
    ]


    def formula_standarized(self,obj):
        if obj.formula is not None:
            return linebreaksbr(obj.formula.text)
        return ''

    """
    def levenshtein_distance(self,obj):
        s1 = ''
        #if hasattr(obj,'formula'):
        if obj.formula is not None:
            s1 = obj.formula.text
        s2 = obj.formula_text

        return distance(s1, s2, weights=(1, 1, 1))
    """

    #inlines = [FormulasInline]


class ManuscriptsAdmin(ImportExportDebateableAdmin):
    resource_class = ManuscriptsResource

    inlines = [ManuscriptBibliographyInline, OriginsInline, ProvenanceInline, ManuscriptBindingMaterialsInline, ManuscriptBindingComponentsInline, ManuscriptGenresInline ]

    list_display= [field.name for field in Manuscripts._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = [
        'name__icontains',
        'rism_id__icontains',
        'foreign_id__icontains',
        'shelf_mark__icontains',
        'common_name__icontains',
        'contemporary_repository_place_uuid__country_today_eng__icontains',
        'contemporary_repository_place_uuid__region_today_eng__icontains',
        'contemporary_repository_place_uuid__city_today_eng__icontains',
        'contemporary_repository_place_uuid__repository_today_eng__icontains',
        'place_of_origin_uuid__country_today_eng__icontains',
        'place_of_origin_uuid__region_today_eng__icontains',
        'place_of_origin_uuid__city_today_eng__icontains',
        'place_of_origin_uuid__repository_today_eng__icontains',
    ]
    #class Media:
    #    js = ('admin/js/vendor/jquery/jquery.min.js', 'admin/js/jquery.init.js',)  # Dołącz pliki JavaScript związane z obsługą popupów


class CllaAdmin(ImportExportDebateableAdmin):
    resource_class = CllaResource
    inlines = []

    list_display= [field.name for field in Clla._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class ProjectsAdmin(ImportExportDebateableAdmin):
    inlines = []

    list_display= [field.name for field in Projects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['name__icontains']

class MSProjectsAdmin(ImportExportDebateableAdmin):
    resource_class = MSProjectsResource
    inlines = []

    list_display= [field.name for field in MSProjects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class FormulasAdmin(ImportExportDebateableAdmin):
    list_display= ('id','text','co_no')

    search_fields = ['text__icontains']##_startswith


class PlacesAdmin(ImportExportDebateableAdmin):
    resource_class = PlacesResource
                                        #if field.name != 'id' 
    list_display= [field.name for field in Places._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = [
        'place_type__icontains',
        'country_today_eng__icontains',
        'region_today_eng__icontains',
        'city_today_eng__icontains',
        'repository_today_eng__icontains',
        'country_historic_eng__icontains',
        'region_historic_eng__icontains',
        'city_historic_eng__icontains',
        'repository_historic_eng__icontains',
    ]

class ScriptNamesAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in ScriptNames._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['name__icontains']


class TimeReferenceAdmin(ImportExportDebateableAdmin):
    resource_class = TimeReferenceResource
    list_display=  [field.name for field in TimeReference._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['time_description__icontains']


class LiturgicalGenresAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in LiturgicalGenres._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['title__icontains']


class LiturgicalGenresNamesAdmin(ImportExportDebateableAdmin):
    resource_class = LiturgicalGenresNamesResource
    list_display=  ['id','genre','title']


class ManuscriptGenresAdmin(ImportExportDebateableAdmin):
    list_display=  ['id','manuscript_uuid','genre_uuid']

    list_filter = [ManuscriptsFilter]


class CodicologyAdmin(ImportExportDebateableAdmin):
    resource_class = CodicologyResource
    list_display=  [field.name for field in Codicology._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
    
    list_filter = [ManuscriptsFilter]

class QuiresForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = Quires
        fields = '__all__'


class QuiresAdmin(ImportExportDebateableAdmin):
    resource_class = QuiresResource
    form = QuiresForm
    readonly_fields = ('digital_page_number',)

    list_display=  [field.name for field in Quires._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]

    search_fields = ['type_of_the_quire__icontains', 'sequence_of_the_quire']


class WatermarksAdmin(ImportExportDebateableAdmin):
    resource_class = WatermarksResource
    list_display=  [field.name for field in Watermarks._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class ManuscriptWatermarksAdmin(ImportExportDebateableAdmin):
    resource_class = ManuscriptWatermarksResource
    list_display=  ['id','manuscript','watermark','where_in_manuscript']

    list_filter = [ManuscriptsFilter]

class MusicNotationNamesAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in MusicNotationNames._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['name__icontains']


class ManuscriptMusicNotationsForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = ManuscriptMusicNotations
        fields = '__all__'

class ManuscriptMusicNotationsAdmin(ImportExportDebateableAdmin):
    resource_class = ManuscriptMusicNotationsResource
    form = ManuscriptMusicNotationsForm
    readonly_fields = ('digital_page_number',)

    list_display=  [field.name for field in ManuscriptMusicNotations._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]


class ManuscriptHandsForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = ManuscriptHands
        fields = '__all__'

class ManuscriptHandsAdmin(ImportExportDebateableAdmin):
    resource_class = ManuscriptHandsResource
    list_display=  [field.name for field in ManuscriptHands._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    readonly_fields = ('digital_page_number',)

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]


class HandsAdmin(ImportExportDebateableAdmin):
    resource_class = HandsResource
    list_display=  [field.name for field in Hands._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class ContentFunctionsAdmin(ImportExportDebateableAdmin):
    resource_class = ContentFunctionsResource
    list_display=  ['id','name','parent_function']

    search_fields = ['name__icontains']


class SectionsAdmin(ImportExportDebateableAdmin):
    resource_class = SectionsResource
    list_display=  ['id','name','parent_section']

    search_fields = ['name__icontains']


class ContributorsAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in Contributors._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['initials__icontains', 'first_name__icontains', 'last_name__icontains']

# NEW
#Origins
class OriginsAdmin(ImportExportDebateableAdmin):
    list_display=  ['manuscript','origins_date','origins_place', 'data_contributor']

    list_filter = [ManuscriptsFilter]

class ProvenanceAdmin(ImportExportDebateableAdmin):
    list_display=  ['manuscript','date_from','date_to','place','timeline_sequence','data_contributor']

    list_filter = [ManuscriptsFilter]


#BindingTypes
class BindingTypesAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in BindingTypes._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#BindingStyles
class BindingStylesAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in BindingStyles._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#BindingMaterials
class BindingMaterialsAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in BindingMaterials._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#ManuscriptBindingMaterials
class ManuscriptBindingMaterialsAdmin(ImportExportDebateableAdmin):
    list_display=  ['id','manuscript','material']

    list_filter = [ManuscriptsFilter]


#BindingComponents
class BindingComponentsAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in BindingComponents._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#ManuscriptBindingComponents
class ManuscriptBindingComponentsAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in ManuscriptBindingComponents._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    list_filter = [ManuscriptsFilter]

#BindingDecorationTypes
class BindingDecorationTypesAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in BindingDecorationTypes._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#ManuscriptBindingDecorations
class ManuscriptBindingDecorationsAdmin(ImportExportDebateableAdmin):
    list_display=  ['id','manuscript','decoration']

    list_filter = [ManuscriptsFilter]

#Binding
class BindingAdmin((CustomDebateableAdmin)):
    list_display=  [field.name for field in Binding._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
    
    list_filter = [ManuscriptsFilter]

class RiteNamesAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in RiteNames._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['name__icontains', 'english_translation__icontains']


class ConditionAdmin(ImportExportDebateableAdmin):
    list_display=  ['manuscript']+[field.name for field in Condition._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    list_filter = [ManuscriptsFilter]


class BibliographyAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in Bibliography._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['title__icontains', 'author__icontains', 'shortname__icontains']


class AttributeDebateForm(forms.ModelForm):
    class Meta:
        model = AttributeDebate
        fields = '__all__'
        widgets = {
            'text': Textarea(attrs={'rows': 6, 'cols': 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        object_uuid_field = self.fields.get('object_uuid')
        if object_uuid_field is not None:
            actions = self._safe_build_object_uuid_actions()
            if actions is not None:
                object_uuid_field.help_text = actions

    def _safe_build_object_uuid_actions(self):
        try:
            return self._build_object_uuid_actions()
        except Exception:
            return None

    def _build_object_uuid_actions(self):
        instance = self.instance
        if not instance or not getattr(instance, 'pk', None) or instance.content_type_id is None:
            return None

        model_class = instance.content_type.model_class()
        if model_class is None:
            return None

        links = []
        add_url = self._get_model_admin_url(model_class, 'add')
        if add_url is not None:
            links.append(self._render_admin_icon_link(add_url, 'icon-addlink.svg', 'Add linked object'))

        target = instance.content_object
        if target is not None:
            for action, icon_name, title in (
                ('change', 'icon-changelink.svg', 'Change linked object'),
                ('delete', 'icon-deletelink.svg', 'Delete linked object'),
                ('history', 'icon-history.svg', 'History linked object'),
            ):
                target_url = self._get_object_admin_url(target, action)
                if target_url is not None:
                    links.append(self._render_admin_icon_link(target_url, icon_name, title))

        if not links:
            return None

        return format_html('Linked object actions: {}', mark_safe(' '.join(str(link) for link in links)))

    def _get_model_admin_url(self, model, action):
        opts = model._meta
        try:
            return reverse(f'admin:{opts.app_label}_{opts.model_name}_{action}')
        except Exception:
            return None

    def _get_object_admin_url(self, obj, action):
        model = obj.__class__
        lookup_value = getattr(obj, 'uuid', None) if _model_prefers_uuid_lookup(model) else obj.pk
        if lookup_value in (None, ''):
            return None

        opts = model._meta
        try:
            return reverse(f'admin:{opts.app_label}_{opts.model_name}_{action}', args=(quote(lookup_value),))
        except Exception:
            return None

    def _render_admin_icon_link(self, url, icon_name, title):
        return format_html(
            '<a href="{}" target="_blank" title="{}"><img src="{}" alt="{}"></a>',
            url,
            title,
            static(f'admin/img/{icon_name}'),
            title,
        )


class AttributeDebateAdmin(ImportExportDebateableAdmin):
    form = AttributeDebateForm
    change_form_template = 'admin/indexerapp/attributedebate/change_form.html'
    list_display=  [field.name for field in AttributeDebate._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
    readonly_fields = ('uuid', 'timestamp',)

class LayoutsForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = Layouts
        fields = '__all__'

class LayoutsAdmin(ImportExportDebateableAdmin):
    form = LayoutsForm
    readonly_fields = ('digital_page_number',)

    list_display=  [field.name for field in Layouts._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]

#Calendar
#Decoration #[ ] TODO Zmienić z admin.ModelAdmin na CustomDebateableAdmin

class CalendarForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = Decoration
        fields = ('__all__')
        widgets = {

            'content_uuid': autocomplete.ListSelect2(url='content-autocomplete', attrs={'style': 'width: 200px;'}),
            'rubric_name_standarized_uuid': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 200px;'})
        }

class CalendarAdmin(ImportExportDebateableAdmin):
    form = CalendarForm

    readonly_fields = ('digital_page_number',)

    list_display=  [field.name for field in Calendar._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]



#FeastRanks
class FeastRanksAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in FeastRanks._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#Colours
class ColoursAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Colours._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#Subjects
class SubjectsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Subjects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


#Characteristics
class CharacteristicsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Characteristics._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#DecorationTechniques
class DecorationTechniquesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in DecorationTechniques._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


#DecorationTypes
class DecorationTypesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in DecorationTypes._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#Decoration #[ ] TODO Zmienić z admin.ModelAdmin na CustomDebateableAdmin
class DecorationForm(forms.ModelForm):
    class Meta:
        model = Decoration
        fields = '__all__'


class DecorationAdmin(ImportExportDebateableAdmin):
    form = DecorationForm
    inlines = [DecorationSubjectsInline, DecorationColoursInline, DecorationCharacteristicsInline]

    readonly_fields = ('digital_page_number',)

    list_display=  ['id','manuscript','original_or_added', 'where_in_ms_from', 'where_in_ms_to', 'decoration_type', 'decoration_subtype', 'ornamented_text' ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]


class DecorationSubjectsAdmin(ImportExportDebateableAdmin):

    form = DecorationSubjectsForm

    list_display=  [field.name for field in DecorationSubjects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class DecorationColoursAdmin(ImportExportDebateableAdmin):

    form = DecorationColoursForm

    list_display=  [field.name for field in DecorationColours._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class DecorationCharacteristicsAdmin(ImportExportDebateableAdmin):

    form = DecorationCharacteristicsForm

    list_display=  [field.name for field in DecorationCharacteristics._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
                             
class ManuscriptBibliographyAdmin(ImportExportDebateableAdmin):
    list_display=  [field.name for field in ManuscriptBibliography._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
    
    list_filter = [ManuscriptsFilter]

class UserOpenAIAPIKeyAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in UserOpenAIAPIKey._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

class ImproveOurDataEntryAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in ImproveOurDataEntry._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class TraditionsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Traditions._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class MassHourAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in MassHour._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['short_name__icontains', 'name__icontains']

class TypeAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Type._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class LayerAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Layer._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['short_name__icontains', 'name__icontains']

class GenreAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Genre._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['short_name__icontains', 'name__icontains']

class SeasonMonthAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in SeasonMonth._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]              

    search_fields = ['short_name__icontains', 'name__icontains']

class WeekAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Week._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]      

    search_fields = ['short_name__icontains', 'name__icontains']

class DayAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Day._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    search_fields = ['short_name__icontains', 'name__icontains']

class CeremonyAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Ceremony._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class TopicAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Topic._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class ContentTopicAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in ContentTopic._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class TextStandarizationAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in TextStandarization._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class AIQueryAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in AIQuery._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Content,ContentAdmin)
admin.site.register(Manuscripts,ManuscriptsAdmin)
admin.site.register(Clla,CllaAdmin)
admin.site.register(Projects,ProjectsAdmin)
admin.site.register(MSProjects,MSProjectsAdmin)
admin.site.register(Formulas,FormulasAdmin)
#admin.site.register(Rites,RitesAdmin)
admin.site.register(Places,PlacesAdmin)
admin.site.register(ScriptNames,ScriptNamesAdmin)
admin.site.register(TimeReference,TimeReferenceAdmin)
admin.site.register(LiturgicalGenres,LiturgicalGenresAdmin)
admin.site.register(LiturgicalGenresNames,LiturgicalGenresNamesAdmin)
admin.site.register(ManuscriptGenres,ManuscriptGenresAdmin)
admin.site.register(Codicology,CodicologyAdmin)
admin.site.register(Quires,QuiresAdmin)
admin.site.register(Watermarks,WatermarksAdmin)
admin.site.register(ManuscriptWatermarks,ManuscriptWatermarksAdmin)
admin.site.register(ManuscriptMusicNotations,ManuscriptMusicNotationsAdmin)
admin.site.register(MusicNotationNames,MusicNotationNamesAdmin)
admin.site.register(Hands,HandsAdmin)
admin.site.register(ManuscriptHands,ManuscriptHandsAdmin)
admin.site.register(Sections,SectionsAdmin)
admin.site.register(ContentFunctions,ContentFunctionsAdmin)
admin.site.register(ManuscriptBindingDecorations,ManuscriptBindingDecorationsAdmin)
admin.site.register(BindingDecorationTypes,BindingDecorationTypesAdmin)
admin.site.register(ManuscriptBindingMaterials,ManuscriptBindingMaterialsAdmin)
admin.site.register(BindingMaterials,BindingMaterialsAdmin)
admin.site.register(BindingComponents,BindingComponentsAdmin)
admin.site.register(ManuscriptBindingComponents,ManuscriptBindingComponentsAdmin)
admin.site.register(Binding,BindingAdmin)
admin.site.register(BindingStyles,BindingStylesAdmin)
admin.site.register(BindingTypes,BindingTypesAdmin)
admin.site.register(Provenance,ProvenanceAdmin)
admin.site.register(Origins,OriginsAdmin)
admin.site.register(Contributors,ContributorsAdmin)
admin.site.register(Bibliography,BibliographyAdmin)
admin.site.register(Condition,ConditionAdmin)
admin.site.register(EditionContent,EditionContentAdmin)
admin.site.register(RiteNames,RiteNamesAdmin)
admin.site.register(AttributeDebate,AttributeDebateAdmin)

admin.site.register(DecorationTypes,DecorationTypesAdmin)
admin.site.register(DecorationTechniques,DecorationTechniquesAdmin)
admin.site.register(Characteristics,CharacteristicsAdmin)
admin.site.register(Subjects,SubjectsAdmin)
admin.site.register(Colours,ColoursAdmin)
admin.site.register(FeastRanks,FeastRanksAdmin)
admin.site.register(Decoration,DecorationAdmin)
admin.site.register(Calendar,CalendarAdmin)
admin.site.register(DecorationSubjects,DecorationSubjectsAdmin)
admin.site.register(DecorationColours,DecorationColoursAdmin)
admin.site.register(DecorationCharacteristics,DecorationCharacteristicsAdmin)
admin.site.register(ManuscriptBibliography,ManuscriptBibliographyAdmin)
admin.site.register(Layouts,LayoutsAdmin)
admin.site.register(UserOpenAIAPIKey,UserOpenAIAPIKeyAdmin)
admin.site.register(ImproveOurDataEntry,ImproveOurDataEntryAdmin)
admin.site.register(Traditions,TraditionsAdmin)

admin.site.register(MassHour,MassHourAdmin)
admin.site.register(Type,TypeAdmin)
admin.site.register(Layer,LayerAdmin)
admin.site.register(Genre,GenreAdmin)
admin.site.register(SeasonMonth,SeasonMonthAdmin)
admin.site.register(Week,WeekAdmin)
admin.site.register(Day,DayAdmin)
admin.site.register(Ceremony,CeremonyAdmin)
admin.site.register(Topic,TopicAdmin)
admin.site.register(ContentTopic,ContentTopicAdmin)
admin.site.register(TextStandarization,TextStandarizationAdmin)
admin.site.register(AIQuery,AIQueryAdmin)


def _ensure_uuid_visible_in_admin():
    for model, model_admin in admin.site._registry.items():
        try:
            model._meta.get_field('uuid')
        except Exception:
            continue

        list_display = tuple(getattr(model_admin, 'list_display', ()))
        if 'uuid' not in list_display:
            model_admin.list_display = list_display + ('uuid',)

        readonly_fields = tuple(getattr(model_admin, 'readonly_fields', ()))
        if 'uuid' not in readonly_fields:
            model_admin.readonly_fields = readonly_fields + ('uuid',)


def _enable_uuid_lookup_in_admin():
    for model, model_admin in admin.site._registry.items():
        if not _model_prefers_uuid_lookup(model):
            continue

        if getattr(model_admin, '_uuid_lookup_enabled', False):
            continue

        original_get_object = model_admin.get_object
        original_get_changelist = model_admin.get_changelist
        original_url_for_result = getattr(model_admin, 'url_for_result', None)
        original_response_add = model_admin.response_add
        original_response_change = model_admin.response_change

        def get_uuid_reference(obj):
            value = getattr(obj, 'uuid', None)
            return quote(value) if value else None

        def rewrite_admin_redirect(response, obj):
            uuid_reference = get_uuid_reference(obj)
            if not uuid_reference or not hasattr(response, 'url') or not response.url:
                return response

            pk_fragment = f'/{quote(obj.pk)}/'
            uuid_fragment = f'/{uuid_reference}/'
            response['Location'] = response.url.replace(pk_fragment, uuid_fragment, 1)
            return response

        def get_object_with_uuid(self, request, object_id, from_field=None, _original_get_object=original_get_object):
            if from_field is None:
                try:
                    parsed_uuid = uuid.UUID(str(object_id).strip())
                except (AttributeError, TypeError, ValueError):
                    parsed_uuid = None

                if parsed_uuid is not None:
                    instance = self.model._default_manager.filter(uuid=parsed_uuid).first()
                    if instance is not None:
                        return instance

            return _original_get_object(request, object_id, from_field=from_field)

        def url_for_result_with_uuid(self, result, _original_url_for_result=original_url_for_result):
            uuid_reference = get_uuid_reference(result)
            if uuid_reference:
                return reverse(
                    'admin:%s_%s_change' % (self.opts.app_label, self.opts.model_name),
                    args=(uuid_reference,),
                    current_app=self.admin_site.name,
                )

            if _original_url_for_result is not None:
                return _original_url_for_result(result)

            return reverse(
                'admin:%s_%s_change' % (self.opts.app_label, self.opts.model_name),
                args=(quote(result.pk),),
                current_app=self.admin_site.name,
            )

        def get_changelist_with_uuid(self, request, _original_get_changelist=original_get_changelist):
            base_changelist = _original_get_changelist(request)
            model_admin_instance = self
            change_list_base = ChangeList

            if isinstance(base_changelist, type) and issubclass(base_changelist, ChangeList):
                change_list_base = base_changelist

            class UUIDChangeList(change_list_base):
                def url_for_result(self, result):
                    return url_for_result_with_uuid(model_admin_instance, result)

            return UUIDChangeList

        def response_add_with_uuid(self, request, obj, _original_response_add=original_response_add):
            return rewrite_admin_redirect(_original_response_add(request, obj), obj)

        def response_change_with_uuid(self, request, obj, _original_response_change=original_response_change):
            return rewrite_admin_redirect(_original_response_change(request, obj), obj)

        model_admin.get_object = MethodType(get_object_with_uuid, model_admin)
        model_admin.get_changelist = MethodType(get_changelist_with_uuid, model_admin)
        setattr(model_admin, 'url_for_result', MethodType(url_for_result_with_uuid, model_admin))
        model_admin.response_add = MethodType(response_add_with_uuid, model_admin)
        model_admin.response_change = MethodType(response_change_with_uuid, model_admin)
        setattr(model_admin, '_uuid_lookup_enabled', True)


_ensure_uuid_visible_in_admin()
_enable_uuid_lookup_in_admin()


def _patch_uuid_related_widget_wrapper():
    if getattr(RelatedFieldWidgetWrapper, '_uuid_lookup_patched', False):
        return

    original_get_context = RelatedFieldWidgetWrapper.get_context

    def get_context_with_uuid(self, name, value, attrs, _original_get_context=original_get_context):
        context = _original_get_context(self, name, value, attrs)
        if not _model_prefers_uuid_lookup(self.rel.model):
            return context

        context['url_params'] = '_to_field=uuid&_popup=1'
        if 'view_related_url_params' in context:
            context['view_related_url_params'] = '_to_field=uuid'
        return context

    RelatedFieldWidgetWrapper.get_context = get_context_with_uuid
    setattr(RelatedFieldWidgetWrapper, '_uuid_lookup_patched', True)


def _patch_uuid_relation_formfields():
    if getattr(BaseModelAdmin, '_uuid_relation_lookup_patched', False):
        return

    original_fk = BaseModelAdmin.formfield_for_foreignkey
    original_m2m = BaseModelAdmin.formfield_for_manytomany

    def formfield_for_foreignkey_with_uuid(self, db_field, request, **kwargs):
        remote_model = getattr(db_field.remote_field, 'model', None)
        if remote_model is not None and _model_prefers_uuid_lookup(remote_model):
            kwargs.setdefault('to_field_name', 'uuid')
        return original_fk(self, db_field, request, **kwargs)

    def formfield_for_manytomany_with_uuid(self, db_field, request, **kwargs):
        remote_model = getattr(db_field.remote_field, 'model', None)
        if remote_model is not None and _model_prefers_uuid_lookup(remote_model):
            kwargs.setdefault('to_field_name', 'uuid')
        return original_m2m(self, db_field, request, **kwargs)

    BaseModelAdmin.formfield_for_foreignkey = formfield_for_foreignkey_with_uuid
    BaseModelAdmin.formfield_for_manytomany = formfield_for_manytomany_with_uuid
    setattr(BaseModelAdmin, '_uuid_relation_lookup_patched', True)


def _patch_uuid_to_field_allowed():
    if getattr(BaseModelAdmin, '_uuid_to_field_allowed_patched', False):
        return

    original_to_field_allowed = BaseModelAdmin.to_field_allowed

    def to_field_allowed_with_uuid(self, request, to_field, _original_to_field_allowed=original_to_field_allowed):
        if to_field == 'uuid' and _model_prefers_uuid_lookup(self.model):
            return True
        return _original_to_field_allowed(self, request, to_field)

    BaseModelAdmin.to_field_allowed = to_field_allowed_with_uuid
    setattr(BaseModelAdmin, '_uuid_to_field_allowed_patched', True)


_patch_uuid_related_widget_wrapper()
_patch_uuid_relation_formfields()
_patch_uuid_to_field_allowed()