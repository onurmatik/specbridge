from django.http import JsonResponse
from django.urls import reverse
from ninja import Router, Schema
from ninja.security import django_auth

from alignment.services import compute_dashboard_metrics
from projects.models import MembershipRole, ProjectInvite, ProjectMembership
from projects.services import create_project_workspace, get_project_or_404, resolve_actor
from specs.models import AuditEventType
from specs.services import log_audit_event

router = Router(tags=["projects"])


class ProjectCreatePayload(Schema):
    project_name: str
    tagline: str | None = None


class InvitePayload(Schema):
    email: str
    role: str = MembershipRole.VIEWER


class MembershipUpdatePayload(Schema):
    role: str | None = None
    title: str | None = None
    is_active: bool | None = None


@router.post("/create", auth=django_auth)
def create_project(request, payload: ProjectCreatePayload):
    errors = {}

    project_name = payload.project_name.strip()
    tagline = (payload.tagline or "").strip()

    if not project_name:
        errors["project_name"] = ["Project name is required."]
    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=422)

    project = create_project_workspace(
        actor=request.user,
        project_name=project_name,
        tagline=tagline,
    )
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


@router.get("/{slug}/stats")
def project_stats(request, slug: str):
    project = get_project_or_404(slug, request.user)
    metrics = compute_dashboard_metrics(project)
    return {
        "project": {
            "id": project.id,
            "slug": project.slug,
            "name": project.name,
            "tagline": project.tagline,
            "status_label": project.status_label,
        },
        "metrics": metrics,
    }


@router.get("/{slug}/memberships")
def list_memberships(request, slug: str):
    project = get_project_or_404(slug, request.user)
    return {
        "items": [
            {
                "id": membership.id,
                "user": membership.user.display_name,
                "email": membership.user.email,
                "role": membership.role,
                "title": membership.title or membership.user.title,
                "is_active": membership.is_active,
            }
            for membership in project.memberships.select_related("user")
        ]
    }


@router.post("/{slug}/memberships/invite", auth=django_auth)
def invite_membership(request, slug: str, payload: InvitePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    invite = ProjectInvite.objects.create(
        project=project,
        email=payload.email,
        role=payload.role,
        invited_by=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.MEMBERSHIP_CHANGED,
        title=f"Invited {invite.email}",
        description=f"Role: {invite.role}",
        metadata={"invite_id": invite.id, "email": invite.email, "role": invite.role},
    )
    return {"id": invite.id, "email": invite.email, "role": invite.role, "status": invite.status}


@router.post("/{slug}/memberships/{membership_id}/update", auth=django_auth)
def update_membership(request, slug: str, membership_id: int, payload: MembershipUpdatePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    membership = project.memberships.select_related("user").get(pk=membership_id)
    if payload.role is not None:
        membership.role = payload.role
    if payload.title is not None:
        membership.title = payload.title
    if payload.is_active is not None:
        membership.is_active = payload.is_active
    membership.save()
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.MEMBERSHIP_CHANGED,
        title=f"Updated membership for {membership.user.display_name}",
        description=f"Role: {membership.role}",
        metadata={"membership_id": membership.id},
    )
    return {"ok": True, "membership_id": membership.id}


@router.post("/{slug}/memberships/{membership_id}/remove", auth=django_auth)
def remove_membership(request, slug: str, membership_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    membership = project.memberships.select_related("user").get(pk=membership_id)
    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.MEMBERSHIP_CHANGED,
        title=f"Deactivated membership for {membership.user.display_name}",
        metadata={"membership_id": membership.id},
    )
    return {"ok": True}
