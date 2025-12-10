from django.contrib import admin
from .models import *

from django.db import models
from django.forms import TextInput, Textarea
from django.core.exceptions import ValidationError
from admin_searchable_dropdown.filters import AutocompleteFilter
#from zotero.admin import TagInlineAdmin

from django import forms

from django.template.defaultfilters import linebreaksbr

#for add debate:
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.html import format_html

from decimal import Decimal
import math

import modelclone

#For filters:
from django.db.models import Q


from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User




########################  FolioPaginationWidget  ###################################

from django.utils.safestring import mark_safe

class HorizontalRadioRenderer(forms.RadioSelect):
    def render(self):
        return mark_safe(u'\n'.join([u'%s\n' % w for w in self]))




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
            'formula': autocomplete.ListSelect2(url='formula-autocomplete', attrs={'style': 'width: 400px;'}),
            'rite': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 400px;'}),
            'genre': autocomplete.ListSelect2(url='genre-autocomplete', attrs={'style': 'width: 400px;'})
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
            'rubric_name_standarized': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 200px;'})
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
    extra = 0

    form = DecorationCharacteristicsForm

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }


class ManuscriptBibliographyInline(admin.TabularInline):
    model = ManuscriptBibliography
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class OriginsInline(admin.TabularInline):
    model = Origins
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class ProvenanceInline(admin.TabularInline):
    model = Provenance
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class ManuscriptBindingMaterialsInline(admin.TabularInline):
    model = ManuscriptBindingMaterials
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

class ManuscriptBindingComponentsInline(admin.TabularInline):
    model = ManuscriptBindingComponents
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }

    

class ManuscriptGenresInline(admin.TabularInline):
    model = ManuscriptGenres
    extra = 0

    show_change_link=True

    formfield_overrides = {
        models.CharField: {'widget': TextInput(attrs={'size':'20'})},
        models.TextField: {'widget': Textarea(attrs={'rows':3, 'cols':40})},
    }


# Formulas filters
class FormulasFilter(AutocompleteFilter):
    title = "Formulas"
    field_name = 'formula'

class FormulaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Formulas.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


# Manuscripts filters
class ManuscriptsFilter(AutocompleteFilter):
    title = "Manuscripts"
    field_name = 'manuscript'

class ManuscriptsAutocomplete(autocomplete.Select2QuerySetView):
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
        debates = AttributeDebate.objects.filter(
            content_type=content_type,
            object_id=obj.pk,
            field_name=db_field_name
        )

        debates_links = [
            f'<a href="#" style="cursor: pointer;" onclick="window.open(\'{reverse("admin:indexerapp_attributedebate_change", args=(debate.id,))}?_popup=1\', \'DebatePopup\', \'height=500,width=800,resizable=yes,scrollbars=yes\'); return false;">{debate.text}</a> '
            f'<a href="#" style="color: red; cursor: pointer;" onclick="window.open(\'{reverse("admin:indexerapp_attributedebate_delete", args=(debate.id,))}?_popup=1\', \'DebateDeletePopup\', \'height=500,width=800,resizable=yes,scrollbars=yes\'); return false;">⌫</a>'
            for debate in debates
        ]
        return debates_links


    def add_debate_link(self, obj, db_field, field):
        debate_add_url = reverse("admin:indexerapp_attributedebate_add")
        content_type = ContentType.objects.get_for_model(obj)
        object_id = obj.pk if obj else 'add'
        content_object = f"{content_type.app_label}_{content_type.model}_{object_id}"
        debate_add_url_with_parameters = f"{debate_add_url}?_popup=1&content_type={content_type.id}&object_id={object_id}&content_object={content_object}&field_name={db_field.name}"

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

class EditionContentAdmin(admin.ModelAdmin):
    form = EditionContentForm

    list_display=  ['id','short_name']+[field.name for field in EditionContent._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    list_filter = [FormulasFilter]
    autocomplete_fields = ['formula']


    def formula_standarized(self,obj):
        if obj.formula is not None:
            return linebreaksbr(obj.formula.text)
        return ''
    
    def short_name(self,obj):
        return str(obj)

# @admin.register(Content)
class ContentAdmin(CustomDebateableAdmin):
    form = ContentForm
    list_display= ['id', 'manuscript', 'formula_text', 'formula_standarized', 'rubric_name_from_ms', 'similarity_levenshtein', 'where_in_ms_from', 'where_in_ms_to', 'original_or_added', 'biblical_reference', 'reference_to_other_items', 'similarity_by_user', 'entry_date', 'sequence_in_ms', 'edition_index', 'comments']


    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]


    #wrapped_field= easy.SimpleAdminField(lambda x: linebreaksbr(x.formula), 'formula', 'formula')

    list_filter = [FormulasFilter, ManuscriptsFilter]
    autocomplete_fields = ['formula', 'manuscript']


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

"""
class ManuscriptsAdmin(admin.ModelAdmin):
    #list_display= ('name','rism_id', 'rites_count')
    list_display= [field.name for field in Manuscripts._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    #inlines = [RitesInline]
    #inlines = (TagInlineAdmin,)

    def rites_count(self,obj):
        return obj.ms_rites.count()
"""


class ManuscriptsAdmin(CustomDebateableAdmin):

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
        'contemporary_repository_place__country_today_eng__icontains',
        'contemporary_repository_place__region_today_eng__icontains',
        'contemporary_repository_place__city_today_eng__icontains',
        'contemporary_repository_place__repository_today_eng__icontains',
        'place_of_origin__country_today_eng__icontains',
        'place_of_origin__region_today_eng__icontains',
        'place_of_origin__city_today_eng__icontains',
        'place_of_origin__repository_today_eng__icontains',
    ]
    #class Media:
    #    js = ('admin/js/vendor/jquery/jquery.min.js', 'admin/js/jquery.init.js',)  # Dołącz pliki JavaScript związane z obsługą popupów


class CllaAdmin(CustomDebateableAdmin):
    inlines = []

    list_display= [field.name for field in Clla._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class ProjectsAdmin(CustomDebateableAdmin):
    inlines = []

    list_display= [field.name for field in Projects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class MSProjectsAdmin(CustomDebateableAdmin):
    inlines = []

    list_display= [field.name for field in MSProjects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class FormulasAdmin(CustomDebateableAdmin):
    list_display= ('id','text','co_no')

    search_fields = ['text__icontains']##_startswith
"""
class RitesAdmin(CustomDebateableAdmin):
    #list_display= ('rubric_name_from_ms','manuscript','rubric_sequence','content_count')

    list_display= [field.name for field in Rites._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    inlines = [ContentInline]

    def content_count(self,obj):
        #if obj.content_set is None:
        #    return 0
        
        return obj.content_set.count()
    

    class Media:
        js = ('js/admin_content_sequence.js',)

"""
"""     def save_formset(self, request, form, formset, change):
        if formset.model == Content:
            # Get the related Rite for the form
            rite = form.instance

            # Calculate the maximum sequence_in_ms for the related Rite
            max_sequence = Content.objects.filter(rite=rite).aggregate(models.Max('sequence_in_ms'))['sequence_in_ms__max']

            if max_sequence is not None:
                max_sequence += 1
            else:
                max_sequence = 1

            for form in formset.forms:
                if form.instance.sequence_in_ms is None:
                    form.instance.sequence_in_ms = max_sequence
                    max_sequence += 1
                form.instance.save()
        
        super(RitesAdmin, self).save_formset(request, form, formset, change)
 """

class PlacesAdmin(admin.ModelAdmin):
                                        #if field.name != 'id' 
    list_display= [field.name for field in Places._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class ScriptNamesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in ScriptNames._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class TimeReferenceAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in TimeReference._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class LiturgicalGenresAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in LiturgicalGenres._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class LiturgicalGenresNamesAdmin(admin.ModelAdmin):
    list_display=  ['id','genre','title']


class ManuscriptGenresAdmin(CustomDebateableAdmin):
    list_display=  ['id','manuscript','genre']

    list_filter = [ManuscriptsFilter]


class CodicologyAdmin(CustomDebateableAdmin):
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


class QuiresAdmin(CustomDebateableAdmin):
    form = QuiresForm
    readonly_fields = ('digital_page_number',)

    list_display=  [field.name for field in Quires._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]


class WatermarksAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Watermarks._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class ManuscriptWatermarksAdmin(CustomDebateableAdmin):
    list_display=  ['id','manuscript','watermark','where_in_manuscript']

    list_filter = [ManuscriptsFilter]

class MusicNotationNamesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in MusicNotationNames._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class ManuscriptMusicNotationsForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = ManuscriptMusicNotations
        fields = '__all__'

class ManuscriptMusicNotationsAdmin(CustomDebateableAdmin):
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

class ManuscriptHandsAdmin(CustomDebateableAdmin):
    list_display=  [field.name for field in ManuscriptHands._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    readonly_fields = ('digital_page_number',)

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]


class HandsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Hands._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class ContentFunctionsAdmin(admin.ModelAdmin):
    list_display=  ['id','name','parent_function']


class SectionsAdmin(admin.ModelAdmin):
    list_display=  ['id','name','parent_section']


class ContributorsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Contributors._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

# NEW
#Origins
class OriginsAdmin(CustomDebateableAdmin):
    list_display=  ['manuscript','origins_date','origins_place', 'data_contributor']

    list_filter = [ManuscriptsFilter]

class ProvenanceAdmin(CustomDebateableAdmin):
    list_display=  ['manuscript','date_from','date_to','place','timeline_sequence','data_contributor']

    list_filter = [ManuscriptsFilter]


#BindingTypes
class BindingTypesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in BindingTypes._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#BindingStyles
class BindingStylesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in BindingStyles._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#BindingMaterials
class BindingMaterialsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in BindingMaterials._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#ManuscriptBindingMaterials
class ManuscriptBindingMaterialsAdmin(CustomDebateableAdmin):
    list_display=  ['id','manuscript','material']

    list_filter = [ManuscriptsFilter]


#BindingComponents
class BindingComponentsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in BindingComponents._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#ManuscriptBindingComponents
class ManuscriptBindingComponentsAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in ManuscriptBindingComponents._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    list_filter = [ManuscriptsFilter]

#BindingDecorationTypes
class BindingDecorationTypesAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in BindingDecorationTypes._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

#ManuscriptBindingDecorations
class ManuscriptBindingDecorationsAdmin(admin.ModelAdmin):
    list_display=  ['id','manuscript','decoration']

    list_filter = [ManuscriptsFilter]

#Binding
class BindingAdmin((CustomDebateableAdmin)):
    list_display=  [field.name for field in Binding._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
    
    list_filter = [ManuscriptsFilter]

class RiteNamesAdmin(CustomDebateableAdmin):
    list_display=  [field.name for field in RiteNames._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class ConditionAdmin(CustomDebateableAdmin):
    list_display=  ['manuscript']+[field.name for field in Condition._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    list_filter = [ManuscriptsFilter]


class BibliographyAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Bibliography._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]


class AttributeDebateAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in AttributeDebate._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class LayoutsForm(forms.ModelForm):
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = Layouts
        fields = '__all__'

class LayoutsAdmin(CustomDebateableAdmin):
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

            'content': autocomplete.ListSelect2(url='content-autocomplete', attrs={'style': 'width: 200px;'}),
            'rubric_name_standarized': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 200px;'})
        }

class CalendarAdmin(CustomDebateableAdmin):
    form = CalendarForm

    readonly_fields = ('digital_page_number',)

    list_display=  [field.name for field in Calendar._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]



#FeastRanks
class FeastRanksAdmin(admin.ModelAdmin):
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
    #where_in_ms_from = FolioPaginationField()
    #where_in_ms_to = FolioPaginationField()

    class Meta:
        model = Decoration
        fields = ('__all__')
        widgets = {

            'content': autocomplete.ListSelect2(url='content-autocomplete', attrs={'style': 'width: 200px;'}),
            'rubric_name_standarized': autocomplete.ListSelect2(url='rites-autocomplete', attrs={'style': 'width: 200px;'})

        }


class DecorationForm(forms.ModelForm):
    class Meta:
        model = Decoration
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter decoration_type to only show DecorationTypes with no parent_type
        self.fields['decoration_type'].queryset = DecorationTypes.objects.filter(parent_type__isnull=True)

        # Filter decoration_subtype to only show DecorationTypes with a parent_type
        self.fields['decoration_subtype'].queryset = DecorationTypes.objects.filter(parent_type__isnull=False)


class DecorationAdmin(CustomDebateableAdmin):
    form = DecorationForm
    inlines = [DecorationSubjectsInline, DecorationColoursInline, DecorationCharacteristicsInline]

    readonly_fields = ('digital_page_number',)

    list_display=  ['id','manuscript','original_or_added', 'where_in_ms_from', 'where_in_ms_to', 'decoration_type', 'decoration_subtype', 'ornamented_text' ]

    #list_display = ["where_in_ms_start" if x == "where_in_ms_from" else x for x in list_display]
    #list_display = ["where_in_ms_end" if x == "where_in_ms_to" else x for x in list_display]

    list_filter = [ManuscriptsFilter]


class DecorationSubjectsAdmin(CustomDebateableAdmin):

    form = DecorationSubjectsForm

    list_display=  [field.name for field in DecorationSubjects._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class DecorationColoursAdmin(CustomDebateableAdmin):

    form = DecorationColoursForm

    list_display=  [field.name for field in DecorationColours._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class DecorationCharacteristicsAdmin(CustomDebateableAdmin):

    form = DecorationCharacteristicsForm

    list_display=  [field.name for field in DecorationCharacteristics._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]
                             
class ManuscriptBibliographyAdmin(CustomDebateableAdmin):
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

class TypeAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Type._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class LayerAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Layer._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class GenreAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Genre._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

class SeasonMonthAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in SeasonMonth._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]              

class WeekAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Week._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]      

class DayAdmin(admin.ModelAdmin):
    list_display=  [field.name for field in Day._meta.fields
                             #if not isinstance(field, models.ForeignKey)
                             ]

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