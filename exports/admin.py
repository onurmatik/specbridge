from django.contrib import admin

from .models import ExportArtifact


@admin.register(ExportArtifact)
class ExportArtifactAdmin(admin.ModelAdmin):
    list_display = ("filename", "project", "format", "status", "share_enabled", "created_at")
    list_filter = ("format", "status", "share_enabled")
