import json
from json import JSONDecodeError

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from projects.demo import ensure_demo_workspace
from projects.invitations import InviteTokenError, InviteTokenExpired, get_invite_for_token
from projects.models import ProjectMembership
from projects.services import (
    assumptions_context,
    create_project_workspace,
    dashboard_context,
    decisions_context,
    get_primary_project,
    get_project_or_404,
    handoff_context,
    history_context,
    members_context,
    navigation_for_project,
    project_directory_issue_summary,
    visible_projects_for_user,
    workspace_context,
)
from specs.models import AuditEventType
from specs.services import log_audit_event


def _project_create_context(request, *, values=None, errors=None):
    has_projects = visible_projects_for_user(request.user).exists()
    resolved_errors = errors or {}
    return {
        "project": None,
        "current_project": None,
        "active_item": "projects",
        "navigation_items": [
            {"key": "projects", "label": "Projects", "icon": "lucide:folder-open", "url": reverse("project-directory")}
        ],
        "unresolved_count": 0,
        "active_members_count": 0,
        "status_label": "No Active Project",
        "page_title": "Create Project",
        "page_breadcrumb_label": "Create Project",
        "page_badge_label": "New workspace" if has_projects else "First workspace",
        "header_variant": "default",
        "header_hide_create_action": True,
        "project_create_values": values or {},
        "project_create_errors": resolved_errors,
        "project_create_summary_errors": resolved_errors.get("__all__", []),
    }


def _wants_json(request):
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
        or request.content_type == "application/json"
    )


def _project_create_payload(request):
    if request.content_type == "application/json":
        raw_body = request.body.decode("utf-8").strip()
        return json.loads(raw_body or "{}")
    return request.POST


def _project_create_response_payload(project):
    return {
        "ok": True,
        "project": {
            "id": project.id,
            "slug": project.slug,
            "name": project.name,
            "status_label": project.status_label,
        },
        "redirect_to": reverse("project-workspace", args=[project.slug]),
    }


@ensure_csrf_cookie
def project_directory(request):
    if not request.user.is_authenticated:
        ensure_demo_workspace()
    projects = list(
        visible_projects_for_user(request.user)
        .prefetch_related("concerns", "consistency_issues")
        .order_by("-last_activity_at", "-updated_at", "name")
    )
    for listed_project in projects:
        listed_project.directory_issue_summary = project_directory_issue_summary(listed_project)
    current_project = projects[0] if projects else None
    if request.user.is_authenticated and current_project is None:
        return redirect(reverse("project-create"))
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
            "header_variant": "project-directory-toolbar",
            "page_breadcrumb_label": "All",
        },
    )


def shortcut_redirect(request, destination):
    project = get_primary_project(request.user)
    if project is None:
        if request.user.is_authenticated:
            return redirect(reverse("project-create"))
        return redirect(reverse("project-directory"))
    return redirect(reverse(destination, args=[project.slug]))


@login_required
@ensure_csrf_cookie
def project_create(request):
    return render(request, "pages/project_create.html", _project_create_context(request))


@login_required
@require_POST
@ensure_csrf_cookie
def project_create_submit(request):
    wants_json = _wants_json(request)
    try:
        payload = _project_create_payload(request)
    except JSONDecodeError:
        errors = {"__all__": ["Invalid request payload. Refresh and try again."]}
        if wants_json:
            return JsonResponse({"ok": False, "errors": errors}, status=400)
        return render(
            request,
            "pages/project_create.html",
            _project_create_context(request, errors=errors),
            status=400,
        )

    project_name = (payload.get("project_name") or "").strip()
    tagline = (payload.get("tagline") or "").strip()
    errors = {}
    if not project_name:
        errors["project_name"] = ["Project name is required."]

    if errors:
        if wants_json:
            return JsonResponse({"ok": False, "errors": errors}, status=422)
        return render(
            request,
            "pages/project_create.html",
            _project_create_context(
                request,
                values={"project_name": project_name, "tagline": tagline},
                errors=errors,
            ),
            status=422,
        )

    project = create_project_workspace(
        actor=request.user,
        project_name=project_name,
        tagline=tagline,
    )
    response_payload = _project_create_response_payload(project)
    if wants_json:
        return JsonResponse(response_payload)
    return redirect(response_payload["redirect_to"])


def project_workspace(request, slug):
    project = get_project_or_404(slug, request.user)
    context = workspace_context(
        project,
        active_concern_id=request.GET.get("concern"),
        active_section_id=request.GET.get("section"),
        stream_filter=request.GET.get("stream"),
    )
    if request.GET.get("_fragment") == "workspace-live":
        return render(request, "pages/workspace_live_fragment.html", context)
    return render(request, "pages/workspace.html", context)


def project_dashboard(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/dashboard.html", dashboard_context(project))


def project_decisions(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/decisions.html", decisions_context(project))


def project_history(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(
        request,
        "pages/history.html",
        history_context(project, active_section_id=request.GET.get("section")),
    )


def project_handoff(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/handoff.html", handoff_context(project))


def project_assumptions(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/assumptions.html", assumptions_context(project))


def project_members(request, slug):
    project = get_project_or_404(slug, request.user)
    return render(request, "pages/members.html", members_context(project))


def project_invite_accept(request, token):
    try:
        invite = get_invite_for_token(token)
    except InviteTokenExpired:
        return render(request, "pages/invite_accept.html", {"invite_state": "expired"}, status=410)
    except InviteTokenError as exc:
        raise Http404(str(exc)) from exc

    if invite.status == "revoked":
        return render(
            request,
            "pages/invite_accept.html",
            {"invite_state": "revoked", "invite": invite},
            status=410,
        )

    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.get_full_path()}")

    if (request.user.email or "").strip().lower() != invite.email.strip().lower():
        return render(
            request,
            "pages/invite_accept.html",
            {"invite_state": "wrong-account", "invite": invite},
            status=403,
        )

    if invite.status == "accepted":
        return redirect(reverse("project-workspace", args=[invite.project.slug]))

    with transaction.atomic():
        membership, created = ProjectMembership.objects.get_or_create(
            project=invite.project,
            user=request.user,
            defaults={
                "role": invite.role,
                "title": request.user.title or "Invited collaborator",
                "is_active": True,
            },
        )
        if not created:
            membership.role = invite.role
            membership.is_active = True
            if not membership.title:
                membership.title = request.user.title or "Invited collaborator"
            membership.save(update_fields=["role", "title", "is_active", "updated_at"])

        invite.accepted_at = timezone.now()
        invite.save(update_fields=["accepted_at", "updated_at"])
        log_audit_event(
            project=invite.project,
            actor=request.user,
            event_type=AuditEventType.MEMBERSHIP_CHANGED,
            title=f"Accepted invite for {invite.email}",
            description=f"Role: {invite.role}",
            metadata={"invite_id": invite.id, "membership_id": membership.id, "action": "accept"},
        )

    return redirect(reverse("project-workspace", args=[invite.project.slug]))
