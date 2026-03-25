from django.contrib import admin

from .models import Organization, Project, ProjectInvite, ProjectMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "slug", "status_label", "updated_at")
    list_filter = ("organization",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "role", "title", "is_active")
    list_filter = ("role", "is_active")


@admin.register(ProjectInvite)
class ProjectInviteAdmin(admin.ModelAdmin):
    list_display = ("email", "project", "role", "status", "created_at")
    list_filter = ("role",)
