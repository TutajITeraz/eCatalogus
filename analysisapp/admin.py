from django.contrib import admin
from django.utils.html import format_html

from .models import AnalysisArtifact, AnalysisRun


class AnalysisArtifactInline(admin.TabularInline):
    model = AnalysisArtifact
    extra = 0
    can_delete = False
    readonly_fields = ('cohort', 'cohort_label', 'kind', 'path', 'size_bytes', 'meta')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AnalysisRun)
class AnalysisRunAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'status', 'progress_bar', 'stage', 'created_at', 'finished_at',
                    'created_by')
    list_filter = ('status', 'pipeline_version')
    search_fields = ('uuid', 'stage')
    readonly_fields = ('uuid', 'status', 'progress', 'stage', 'created_at', 'started_at',
                       'finished_at', 'celery_task_id', 'summary', 'error', 'pipeline_version')
    inlines = [AnalysisArtifactInline]

    @admin.display(description='Progress')
    def progress_bar(self, obj):
        return format_html(
            '<div style="background:#efe6de;width:110px;height:10px;border-radius:5px;'
            'overflow:hidden"><div style="background:#795a42;width:{}%;height:10px"></div>'
            '</div>{}%', obj.progress, obj.progress,
        )

    def has_add_permission(self, request):
        # Runs are started from the corpus analysis page or the management command,
        # both of which set the parameters a run needs.
        return False


@admin.register(AnalysisArtifact)
class AnalysisArtifactAdmin(admin.ModelAdmin):
    list_display = ('run', 'cohort', 'kind', 'size_bytes', 'created_at')
    list_filter = ('cohort', 'kind')
    search_fields = ('run__uuid', 'kind')

    def has_add_permission(self, request):
        return False
