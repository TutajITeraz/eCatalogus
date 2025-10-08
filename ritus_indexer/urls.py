"""ritus_indexer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include,path
from indexerapp import views

#from indexerapp import views #nie wiem czy to zgodne ze sztuką

from rest_framework import routers

from django.views.static import serve 
from django.conf import settings
from django.conf.urls.static import static

from iommi import Form
from iommi import Table
from indexerapp.models import Manuscripts
from indexerapp.models import Content

from iommi.admin import Admin

class IommiAdmin(Admin):

    class Meta:
        """
        apps__admin_logentry__include = True	
        apps__contenttypes_contenttype__include = True

        apps__auth_group_permissions__include = True
        apps__auth_permission__include = True
        apps__auth_user_groups__include = True
        apps__auth_user_user_permissions__include = True

        apps__sessions_session__include = True
        """
        apps__indexerapp_attributedebate__include = True
        apps__indexerapp_bibliography__include = True
        apps__indexerapp_bindingdecorationtypes__include = True
        apps__indexerapp_bindingmaterials__include = True
        apps__indexerapp_bindingstyles__include = True
        apps__indexerapp_bindingtypes__include = True
        apps__indexerapp_binding__include = True
        apps__indexerapp_clla__include = True
        apps__indexerapp_calendar__include = True
        apps__indexerapp_codicology__include = True
        apps__indexerapp_colours__include = True
        apps__indexerapp_condition__include = True
        apps__indexerapp_content__include = True
        apps__indexerapp_contentfunctions__include = True
        apps__indexerapp_contributors__include = True
        apps__indexerapp_decoration__include = True
        apps__indexerapp_characteristics__include = True
        apps__indexerapp_decorationsubjects__include = True
        apps__indexerapp_decorationtechniques__include = True
        apps__indexerapp_decorationtypes__include = True
        apps__indexerapp_feastranks__include = True
        apps__indexerapp_formulas__include = True
        apps__indexerapp_hands__include = True
        apps__indexerapp_layouts__include = True
        apps__indexerapp_liturgicalgenres__include = True
        apps__indexerapp_liturgicalgenresnames__include = True
        apps__indexerapp_manuscriptbibliography__include = True
        apps__indexerapp_manuscriptbindingdecorations__include = True
        apps__indexerapp_manuscriptbindingmaterials__include = True
        apps__indexerapp_manuscriptgenres__include = True
        apps__indexerapp_manuscripthands__include = True
        apps__indexerapp_manuscriptmusicnotations__include = True
        apps__indexerapp_msprojects__include = True
        apps__indexerapp_manuscriptwatermarks__include = True
        apps__indexerapp_manuscripts__include = True
        apps__indexerapp_musicnotationnames__include = True
        apps__indexerapp_origins__include = True
        apps__indexerapp_places__include = True
        apps__indexerapp_projects__include = True
        apps__indexerapp_provenance__include = True
        apps__indexerapp_quires__include = True
        apps__indexerapp_ritenames__include = True
        apps__indexerapp_scriptnames__include = True
        apps__indexerapp_sections__include = True
        apps__indexerapp_subjects__include = True
        apps__indexerapp_timereference__include = True
        apps__indexerapp_useropenaiapikey__include = True
        apps__indexerapp_watermarks__include = True
        apps__indexerapp_binding_authors__include = True
        apps__indexerapp_calendar_authors__include = True
        apps__indexerapp_codicology_authors__include = True
        apps__indexerapp_condition_authors__include = True
        apps__indexerapp_content_authors__include = True
        apps__indexerapp_decoration_authors__include = True
        apps__indexerapp_editioncontent__include = True
        apps__indexerapp_editioncontent_authors__include = True
        apps__indexerapp_layouts_authors__include = True
        apps__indexerapp_manuscripthands_authors__include = True
        apps__indexerapp_manuscriptmusicnotations_authors__include = True
        apps__indexerapp_manuscripts_authors__include = True
        apps__indexerapp_origins_authors__include = True
        apps__indexerapp_provenance_authors__include = True
        apps__indexerapp_quires_authors__include = True
        apps__indexerapp_watermarks_authors__include = True 


    @staticmethod
    def has_permission(request, operation, model=None, instance=None):
        # This is the default implementation
        return request.user.is_staff


router = routers.DefaultRouter()
router.register(r'content', views.ContentViewSet)
router.register(r'hands', views.ManuscriptHandsViewSet, basename='hands')
router.register(r'manuscripts', views.ManuscriptsViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("data-browser/", include("data_browser.urls")),
    path('', views.Index.as_view(), name='index'),
    path('ms/', views.manuscript, name='manuscript'),
    path('login/', views.Login.as_view(), name='login'),
    path('ajax_login/', views.AjaxLoginView.as_view(), name='ajax_login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('ajax_register/', views.AjaxRegisterView.as_view(), name='ajax_register'),
    path('ajax_change_password/', views.AjaxChangePasswordView.as_view(), name='ajax_change_password'),
    path('get_api_key/', views.GetAPIKeyView.as_view(), name='get_api_key'),
    path('set_api_key/', views.SetAPIKeyView.as_view(), name='set_api_key'), 

    path('manuscripts/', views.ManuscriptsView.as_view(), name='manuscripts'),
    path('manuscripts/<int:pk>/', views.ManuscriptDetail.as_view(), name='manuscript-detail'),
    #path('autocomplete/', views.AutocompleteView.as_view(), name='content_autocomplete'),

    #autocomplete:
    path('formula-autocomplete/',views.FormulaAutocomplete.as_view(),name='formula-autocomplete'),
    path('traditions-autocomplete/',views.TraditionsAutocomplete.as_view(),name='traditions-autocomplete'),
    path('liturgical-genres-autocomplete/',views.LiturgicalGenresAutocomplete.as_view(),name='liturgical-genres-autocomplete'),


    path('subject-autocomplete/',views.SubjectAutocomplete.as_view(),name='subject-autocomplete'),
    path('content-autocomplete/',views.ContentAutocomplete.as_view(),name='content-autocomplete'),
    path('rites-autocomplete/',views.RiteNamesAutocomplete.as_view(),name='rites-autocomplete'),
    path('genre-autocomplete/',views.GenreAutocomplete.as_view(),name='genre-autocomplete'),
    path('manuscripts-autocomplete/',views.ManuscriptsAutocomplete.as_view(),name='manuscripts-autocomplete'),
    path('manuscripts-autocomplete-main/',views.ManuscriptsAutocompleteMain.as_view(),name='manuscripts-autocomplete-main'),
    path('contributors-autocomplete/',views.ContributorsAutocomplete.as_view(),name='contributors-autocomplete'),

    path('clla-provenance-autocomplete/',views.CllaProvenanceAutocomplete.as_view(),name='clla-provenance-autocomplete'),
    path('clla-liturgical-genre-autocomplete/',views.CllaLiturgicalGenreAutocomplete.as_view(),name='clla-liturgical-genre-autocomplete'),

    path('ms-foreign-id-autocomplete/',views.MSForeignIdAutocomplete.as_view(),name='ms-foreign-id-autocomplete'),
    path('ms-contemporary-repository-place-autocomplete/',views.MSContemporaryRepositoryPlaceAutocomplete.as_view(),name='ms-contemporary-repository-place-autocomplete'),
    path('ms-shelf-mark-autocomplete/',views.MSShelfMarkAutocomplete.as_view(),name='ms-shelf-mark-autocomplete'),
    path('ms-dating-autocomplete/',views.MSDatingAutocomplete.as_view(),name='ms-dating-autocomplete'),
    path('ms-place-of-origins-autocomplete/',views.MSPlaceOfOriginsAutocomplete.as_view(),name='ms-place-of-origins-autocomplete'),
    path('ms-provenance-autocomplete/',views.MSProvenanceAutocomplete.as_view(),name='ms-provenance-autocomplete'),
    path('ms-main-script-autocomplete/',views.MSMainScriptAutocomplete.as_view(),name='ms-main-script-autocomplete'),
    path('ms-binding-date-autocomplete/',views.MSBindingDateAutocomplete.as_view(),name='ms-binding-date-autocomplete'),



    path('colours-autocomplete/',views.ColoursAutocomplete.as_view(),name='colours-autocomplete'),
    path('script-names-autocomplete/',views.ScriptNamesAutocomplete.as_view(),name='script-names-autocomplete'),
    path('places-autocomplete/',views.PlacesAutocomplete.as_view(),name='places-autocomplete'),
    path('places-countries-autocomplete/',views.PlacesCountriesAutocomplete.as_view(),name='places-countries-autocomplete'),
    path('characteristics-autocomplete/',views.CharacteristicsAutocomplete.as_view(),name='characteristics-autocomplete'),

    path('binding-types-autocomplete/',views.BindingTypesAutocomplete.as_view(),name='binding-types-autocomplete'),
    path('binding-styles-autocomplete/',views.BindingStylesAutocomplete.as_view(),name='binding-styles-autocomplete'),
    path('binding-materials-autocomplete/',views.BindingMaterialsAutocomplete.as_view(),name='binding-materials-autocomplete'),
    path('binding-decoration-type-autocomplete/',views.BindingDecorationTypeAutocomplete.as_view(),name='binding-decoration-type-autocomplete/'),
    path('binding-components-autocomplete/',views.BindingComponentsAutocomplete.as_view(),name='binding-components-autocomplete/'),
    path('binding-category-autocomplete/',views.BindingCategoryAutocomplete.as_view(),name='binding-category-autocomplete/'),

    path('bibliography-title-autocomplete/',views.BibliographyTitleAutocomplete.as_view(),name='bibliography-title-autocomplete'),
    path('bibliography-author-autocomplete/',views.BibliographyAuthorAutocomplete.as_view(),name='bibliography-author-autocomplete'),

    path('ritenames-autocomplete/',views.RiteNamesAutocomplete.as_view(),name='ritenames-autocomplete'),
    path('formulas-autocomplete/',views.FormulasAutocomplete.as_view(),name='formulas-autocomplete'),

    #New [ ]TODO:
    path('decoration-type-autocomplete/',views.DecorationTypeAutocomplete.as_view(),name='decoration-type-autocomplete'),
    path('decoration-subtype-autocomplete/',views.DecorationSubtypeAutocomplete.as_view(),name='decoration-subtype-autocomplete'),
    #DecorationTechniques
    path('decoration-techniques-autocomplete/',views.DecorationTechniquesAutocomplete.as_view(),name='decoration-techniques-autocomplete'),
    path('decoration-ornamented_text-autocomplete/',views.DecorationOrnamentedTextAutocomplete.as_view(),name='decoration-ornamented_text-autocomplete'),


    #ajax:
    path('main_info/', views.MainInfoAjaxView.as_view(), name='main_info'),
    path('ms_info/', views.MSInfoAjaxView.as_view(), name='ms_info'),
    path('codicology_info/', views.CodicologyAjaxView.as_view(), name='codicology_info'),
    path('layouts_info/', views.LayoutsAjaxView.as_view(), name='layouts_info'),
    path('music_notation_info/', views.MusicNotationAjaxView.as_view(), name='music_notation_info'),
    path('provenance_info/', views.ProvenanceAjaxView.as_view(), name='provenance_info'),
    path('bibliography_info/', views.BibliographyAjaxView.as_view(), name='bibliography_info'),
    path('decoration_info/', views.DecorationAjaxView.as_view(), name='decoration_info'),
    path('quires_info/', views.QuiresAjaxView.as_view(), name='quires_info'),
    path('condition_info/', views.ConditionAjaxView.as_view(), name='condition_info'),
    path('clla_info/', views.CllaAjaxView.as_view(), name='clla_info'),
    path('origins_info/', views.OriginsAjaxView.as_view(), name='origins_info'),
    path('binding_info/', views.BindingAjaxView.as_view(), name='binding_info'),
    path('hands_info/', views.HandsAjaxView.as_view(), name='hands_info'),
    path('watermarks_info/', views.WatermarksAjaxView.as_view(), name='watermarks_info'),

    path('assistant/', views.assistantAjaxView.as_view(), name='assistant'),

    path('compare_graph/', views.contentCompareGraph.as_view(), name='compare_graph'),
    path('compare_edition_graph/', views.contentCompareEditionGraph.as_view(), name='compare_edition_graph'),
    path('compare_edition_json/', views.contentCompareEditionJSON.as_view(), name='compare_edition_json'),
    path('compare_formulas_json/', views.contentCompareJSON.as_view(), name='compare_formulas_json'),


    path('rites_lookup/', views.MSRitesLookupView.as_view(), name='rites_lookup'),

    

    path('content_import/', views.ContentImportView.as_view(), name='content_import'),
    path('manuscripts_import/', views.ManuscriptsImportView.as_view(), name='manuscripts_import'),
    path('bibliography_import/', views.BibliographyImportView.as_view(), name='bibliography_import'),
    path('editioncontent_import/', views.EditionContentImportView.as_view(), name='editioncontent_import'),
    path('formulas_import/', views.FormulasImportView.as_view(), name='formulas_import'),
    path('ritenames_import/', views.RiteNamesImportView.as_view(), name='ritenames_import'),
    path('timereference_import/', views.TimeReferenceImportView.as_view(), name='timereference_import'),
    path('places_import/', views.PlacesImportView.as_view(), name='places_import'),
    path('clla_import/', views.CllaImportView.as_view(), name='clla_import'),

    path('bibliography_export/', views.BibliographyExportView.as_view(), name="bibliography_export"),
    path('bibliography_print/', views.BibliographyPrintView.as_view(), name="bibliography_print"),

    path('iommi-form-test/', Form.create(auto__model=Manuscripts).as_view()),
    path('iommi-table-test/', Table(auto__model=Content).as_view()),
    path('iommi-admin/', include(IommiAdmin.urls())),

    path('ms_tei/',views.ManuscriptTEIView.as_view(), name='ms_tei'),
    path('manuscript_tei/', views.ManuscriptTEI.as_view(), name='manuscript_tei_xml'),


    #path('ms_music_notation/<int:pk>/', views.MSMusicNotationView.as_view(), name='ms_music_notation'),
    #path('ms_content/<int:pk>/', views.MSContentView.as_view(), name='ms_content_view'),
    path('api/', include(router.urls)),

    path('export/content/<int:manuscript_id>/', views.ContentCSVExportView.as_view(), name='content_csv_export'),
    path('delete/content/<int:manuscript_id>/', views.DeleteContentView.as_view(), name='delete_content'),
    
    path('delete/tradition-formulas/<int:tradition_id>/', views.DeleteTraditionFromFormulaView.as_view(), name='delete_tradition_from_formula'),
    path('assign-ms-content-to-tradition/<int:manuscript_id>/<int:tradition_id>/', views.AssignMSContentToTraditionView.as_view(), name='assign_ms_content_to_tradition'),


    path(
        'iommi-page-test/',
        views.TestPage().as_view()
    ),

    path('captcha/', include('captcha.urls')),
    path('improve_our_data/', views.ImproveOurDataFormView.as_view(), name='improve_our_data_form'),
]


#if settings.DEBUG:
#        urlpatterns += static(settings.MEDIA_URL,
#                              document_root=settings.MEDIA_ROOT)

urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)