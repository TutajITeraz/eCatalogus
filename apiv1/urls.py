from django.urls import path

from . import views


app_name = 'apiv1'

urlpatterns = [
    path('', views.RootView.as_view(), name='root'),
    path('whoami/', views.WhoAmIView.as_view(), name='whoami'),

    path('manuscripts/', views.ManuscriptListView.as_view(), name='manuscript-list'),
    path('manuscripts/<uuid:manuscript_uuid>/package/',
         views.ManuscriptPackageView.as_view(), name='manuscript-package'),
    path('manuscripts/<uuid:manuscript_uuid>/content/',
         views.ManuscriptContentView.as_view(), name='manuscript-content'),
    path('manuscripts/<uuid:manuscript_uuid>/content/summary/',
         views.ManuscriptContentSummaryView.as_view(), name='manuscript-content-summary'),
    path('manuscripts/<uuid:manuscript_uuid>/content/bulk/',
         views.ManuscriptContentBulkView.as_view(), name='manuscript-content-bulk'),

    path('dictionaries/', views.DictionaryListView.as_view(), name='dictionary-list'),
    path('dictionaries/<slug:slug>/', views.DictionaryDetailView.as_view(), name='dictionary-detail'),
]
