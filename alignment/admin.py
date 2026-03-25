from django.contrib import admin

from .models import Blocker, Decision, DecisionApproval, OpenQuestion, StreamPost


@admin.register(StreamPost)
class StreamPostAdmin(admin.ModelAdmin):
    list_display = ("project", "actor_name", "kind", "created_at")
    list_filter = ("kind", "project")


@admin.register(OpenQuestion)
class OpenQuestionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "severity", "status", "created_at")
    list_filter = ("severity", "status")


@admin.register(Blocker)
class BlockerAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "severity", "status", "created_at")
    list_filter = ("severity", "status")


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "project", "status", "implementation_progress")
    list_filter = ("status",)


@admin.register(DecisionApproval)
class DecisionApprovalAdmin(admin.ModelAdmin):
    list_display = ("decision", "approver", "approved", "created_at")
