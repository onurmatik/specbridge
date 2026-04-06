from django.contrib import admin

from .models import (
    Assumption,
    AuditEvent,
    ConsistencyIssue,
    ConsistencyRun,
    ProjectRevision,
    ProjectSpecDocument,
    SpecDocumentRevision,
)


@admin.register(Assumption)
class AssumptionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "impact", "created_at")
    list_filter = ("status",)


@admin.register(ProjectRevision)
class ProjectRevisionAdmin(admin.ModelAdmin):
    list_display = ("project", "number", "title", "created_at")


@admin.register(ProjectSpecDocument)
class ProjectSpecDocumentAdmin(admin.ModelAdmin):
    list_display = ("project", "title", "schema_version", "updated_at")


@admin.register(SpecDocumentRevision)
class SpecDocumentRevisionAdmin(admin.ModelAdmin):
    list_display = ("spec_document", "number", "title", "created_at")


@admin.register(ConsistencyRun)
class ConsistencyRunAdmin(admin.ModelAdmin):
    list_display = ("project", "provider", "model", "status", "issue_count", "analyzed_at")
    list_filter = ("status", "provider")


@admin.register(ConsistencyIssue)
class ConsistencyIssueAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "severity", "status", "last_seen_at")
    list_filter = ("severity", "status")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("project", "event_type", "title", "created_at")
    list_filter = ("event_type",)
