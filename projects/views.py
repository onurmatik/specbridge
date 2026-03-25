from django.shortcuts import redirect, render
from django.urls import reverse

from projects.demo import ensure_demo_workspace
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
    visible_projects_for_user,
    workspace_context,
)


def project_directory(request):
    if not request.user.is_authenticated:
        ensure_demo_workspace()
    projects = list(visible_projects_for_user(request.user).order_by("-last_activity_at", "-updated_at", "name"))
    current_project = projects[0] if projects else None
    navigation_items = (
        navigation_for_project(current_project)
        if current_project
        else [{"key": "projects", "label": "Projects", "icon": "lucide:folder-open", "url": reverse("project-directory")}]
    )
    return render(
        request,
        "pages/project_directory.html",
        {
            "projects": projects,
            "current_project": current_project,
            "project": current_project,
            "active_item": "projects",
            "navigation_items": navigation_items,
            "unresolved_count": (
                current_project.questions.exclude(status="resolved").count()
                + current_project.blockers.exclude(status="resolved").count()
            )
            if current_project
            else 0,
            "active_members_count": current_project.memberships.filter(is_active=True).count() if current_project else 0,
            "status_label": current_project.status_label if current_project else "No Active Project",
        },
    )


def shortcut_redirect(request, destination):
    project = get_primary_project(request.user)
    if project is None:
        return redirect(reverse("project-directory"))
    return redirect(reverse(destination, args=[project.slug]))


def project_workspace(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/workspace.html", workspace_context(project))


def project_dashboard(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/dashboard.html", dashboard_context(project))


def project_decisions(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/decisions.html", decisions_context(project))


def project_history(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/history.html", history_context(project))


def project_handoff(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/handoff.html", handoff_context(project))


def project_assumptions(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/assumptions.html", assumptions_context(project))


def project_members(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/members.html", members_context(project))
