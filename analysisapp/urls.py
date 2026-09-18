from django.urls import path

from . import views

app_name = 'analysis'

urlpatterns = [
    path('runs/', views.AnalysisRunListView.as_view(), name='run-list'),
    path('runs/start/', views.AnalysisRunStartView.as_view(), name='run-start'),
    path('manuscripts/', views.AnalysisManuscriptListView.as_view(), name='manuscript-list'),
    path('runs/<uuid:run_uuid>/', views.AnalysisRunDetailView.as_view(), name='run-detail'),
    path('runs/<uuid:run_uuid>/<slug:cohort>/<slug:kind>/',
         views.AnalysisArtifactView.as_view(), name='artifact'),
    path('formulas/', views.FormulaLookupView.as_view(), name='formula-lookup'),
]
