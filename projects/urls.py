from django.urls import path

from exports import views as export_views
from projects import views


urlpatterns = [
    path("", views.project_directory, name="project-directory"),
    path("invites/<str:token>/", views.project_invite_accept, name="project-invite-accept"),
    path("projects/create/", views.project_create, name="project-create"),
    path("projects/create/submit/", views.project_create_submit, name="project-create-submit"),
    path("dashboard/", views.shortcut_redirect, {"destination": "project-dashboard"}, name="dashboard-shortcut"),
    path("decisions/", views.shortcut_redirect, {"destination": "project-decisions"}, name="decisions-shortcut"),
    path("history/", views.shortcut_redirect, {"destination": "project-history"}, name="history-shortcut"),
    path("handoff/", views.shortcut_redirect, {"destination": "project-handoff"}, name="handoff-shortcut"),
    path("assumptions/", views.shortcut_redirect, {"destination": "project-assumptions"}, name="assumptions-shortcut"),
    path("members/", views.shortcut_redirect, {"destination": "project-members"}, name="members-shortcut"),
    path("projects/<slug:slug>/workspace/", views.project_workspace, name="project-workspace"),
    path("projects/<slug:slug>/dashboard/", views.project_dashboard, name="project-dashboard"),
    path("projects/<slug:slug>/decisions/", views.project_decisions, name="project-decisions"),
    path("projects/<slug:slug>/history/", views.project_history, name="project-history"),
    path("projects/<slug:slug>/handoff/", views.project_handoff, name="project-handoff"),
    path("projects/<slug:slug>/exports/<int:export_id>/download/", export_views.download_export, name="project-export-download"),
    path("projects/<slug:slug>/assumptions/", views.project_assumptions, name="project-assumptions"),
    path("projects/<slug:slug>/members/", views.project_members, name="project-members"),
]
