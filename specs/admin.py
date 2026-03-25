from django.contrib import admin

from .models import Assumption, AuditEvent, SpecSection, SpecVersion


@admin.register(SpecSection)
class SpecSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "order", "is_required")
    list_filter = ("status", "project")


@admin.register(Assumption)
class AssumptionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "impact", "created_at")
    list_filter = ("status",)


@admin.register(SpecVersion)
class SpecVersionAdmin(admin.ModelAdmin):
    list_display = ("project", "number", "title", "created_at")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("project", "event_type", "title", "created_at")
    list_filter = ("event_type",)
