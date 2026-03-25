from django.shortcuts import redirect, render
from django.urls import reverse

from projects.demo import ensure_demo_workspace
from projects.models import Project
from projects.services import (
    assumptions_context,
    dashboard_context,
    decisions_context,
    get_primary_project,
    get_project_or_404,
    handoff_context,
    history_context,
    members_context,
    navigation_for_project,
    workspace_context,
)


def project_directory(request):
    ensure_demo_workspace()
    projects = Project.objects.select_related("organization").all()
    current_project = get_primary_project()
    return render(
        request,
        "pages/project_directory.html",
        {
            "projects": projects,
            "current_project": current_project,
            "project": current_project,
            "active_item": "projects",
            "navigation_items": navigation_for_project(current_project),
            "unresolved_count": current_project.questions.exclude(status="resolved").count()
            + current_project.blockers.exclude(status="resolved").count(),
            "active_members_count": current_project.memberships.filter(is_active=True).count(),
            "status_label": current_project.status_label,
        },
    )


def shortcut_redirect(request, destination):
    project = get_primary_project()
    return redirect(reverse(destination, args=[project.slug]))


def project_workspace(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/workspace.html", workspace_context(project))


def project_dashboard(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/dashboard.html", dashboard_context(project))


def project_decisions(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/decisions.html", decisions_context(project))


def project_history(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/history.html", history_context(project))


def project_handoff(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/handoff.html", handoff_context(project))


def project_assumptions(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/assumptions.html", assumptions_context(project))


def project_members(request, slug):
    project = get_project_or_404(slug)
    return render(request, "pages/members.html", members_context(project))
