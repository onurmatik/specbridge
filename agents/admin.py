from django.contrib import admin

from .models import AgentSuggestion


@admin.register(AgentSuggestion)
class AgentSuggestionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "related_section_key", "created_at")
    list_filter = ("status",)
