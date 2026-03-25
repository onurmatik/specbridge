from django.urls import path

from projects import views


urlpatterns = [
    path("", views.project_directory, name="project-directory"),
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
    path("projects/<slug:slug>/assumptions/", views.project_assumptions, name="project-assumptions"),
    path("projects/<slug:slug>/members/", views.project_members, name="project-members"),
]
