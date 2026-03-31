from django.urls import path

from .views import (
    ETLDeletedRecordsView,
    ETLDeltaExportView,
    ETLDeltaImportView,
    ETLManuscriptExportView,
    ETLManuscriptImportView,
    ETLManuscriptListView,
    ETLStatusView,
    ETLUIOverviewView,
    ETLUIPeerManuscriptsView,
    ETLUIPullCategoryView,
    ETLUIPullManuscriptView,
)


urlpatterns = [
    path('ui/overview/', ETLUIOverviewView.as_view(), name='etl-ui-overview'),
    path('ui/manuscripts/', ETLUIPeerManuscriptsView.as_view(), name='etl-ui-manuscripts'),
    path('ui/pull-category/', ETLUIPullCategoryView.as_view(), name='etl-ui-pull-category'),
    path('ui/pull-manuscript/', ETLUIPullManuscriptView.as_view(), name='etl-ui-pull-manuscript'),
    path('status/', ETLStatusView.as_view(), name='etl-status'),
    path('manuscripts/list/', ETLManuscriptListView.as_view(), name='etl-manuscript-list'),
    path('manuscripts/export/<uuid:manuscript_uuid>/', ETLManuscriptExportView.as_view(), name='etl-manuscript-export'),
    path('manuscripts/import/', ETLManuscriptImportView.as_view(), name='etl-manuscript-import'),
    path('<str:category>/export/', ETLDeltaExportView.as_view(), name='etl-delta-export'),
    path('<str:category>/import/', ETLDeltaImportView.as_view(), name='etl-delta-import'),
    path('<str:category>/deleted/', ETLDeletedRecordsView.as_view(), name='etl-deleted-records'),
]
