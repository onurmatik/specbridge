import logging

from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema
from ninja.security import django_auth

from alignment.services import compute_dashboard_metrics
from projects.invitations import send_project_invitation_email
from projects.languages import DEFAULT_PROJECT_SPEC_LANGUAGE, is_supported_project_spec_language
from projects.models import MembershipRole, ProjectInvite, ProjectMembership
from projects.services import create_project_workspace, get_project_or_404, resolve_actor, update_project_identity
from specs.models import AuditEventType
from specs.services import log_audit_event

router = Router(tags=["projects"])
logger = logging.getLogger(__name__)


class ProjectCreatePayload(Schema):
    project_name: str
    tagline: str | None = None


class InvitePayload(Schema):
    email: str
    role: str = MembershipRole.VIEWER


class ProjectSettingsPayload(Schema):
    project_name: str
    tagline: str | None = None
    spec_language: str | None = None


class MembershipUpdatePayload(Schema):
    role: str | None = None
    title: str | None = None
    is_active: bool | None = None


def serialize_invite(invite: ProjectInvite):
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "status": invite.status,
        "last_sent_at": invite.last_sent_at.isoformat() if invite.last_sent_at else None,
        "revoked_at": invite.revoked_at.isoformat() if invite.revoked_at else None,
        "accepted_at": invite.accepted_at.isoformat() if invite.accepted_at else None,
    }


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
            "spec_language": project.spec_language,
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


@router.post("/{slug}/settings", auth=django_auth)
def update_project_settings(request, slug: str, payload: ProjectSettingsPayload):
    project = get_project_or_404(slug, request.user)
    project_name = payload.project_name.strip()
    tagline = (payload.tagline or "").strip()
    spec_language = (payload.spec_language or project.spec_language or DEFAULT_PROJECT_SPEC_LANGUAGE).strip()
    errors = {}

    if not project_name:
        errors["project_name"] = ["Project name is required."]
    if not is_supported_project_spec_language(spec_language):
        errors["spec_language"] = ["Choose a supported spec language."]

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=422)

    updated_project = update_project_identity(
        project=project,
        project_name=project_name,
        tagline=tagline,
        spec_language=spec_language,
    )
    return {
        "ok": True,
        "project": {
            "id": updated_project.id,
            "slug": updated_project.slug,
            "name": updated_project.name,
            "tagline": updated_project.tagline,
            "summary": updated_project.summary,
            "spec_language": updated_project.spec_language,
            "status_label": updated_project.status_label,
        },
    }


@router.post("/{slug}/memberships/invite", auth=django_auth)
def invite_membership(request, slug: str, payload: InvitePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        with transaction.atomic():
            invite = ProjectInvite.objects.create(
                project=project,
                email=payload.email,
                role=payload.role,
                invited_by=actor,
            )
            send_project_invitation_email(invite, request=request)
            invite.mark_sent()
            invite.save(update_fields=["last_sent_at", "updated_at"])
            log_audit_event(
                project=project,
                actor=actor,
                event_type=AuditEventType.MEMBERSHIP_CHANGED,
                title=f"Invited {invite.email}",
                description=f"Role: {invite.role}",
                metadata={"invite_id": invite.id, "email": invite.email, "role": invite.role},
            )
    except Exception:
        logger.exception("Failed to send invitation email", extra={"project_slug": project.slug, "email": payload.email})
        return JsonResponse(
            {"ok": False, "errors": {"email": ["Invitation email could not be delivered. Check email settings and try again."]}},
            status=502,
        )
    return serialize_invite(invite)


@router.post("/{slug}/memberships/invites/{invite_id}/resend", auth=django_auth)
def resend_invite(request, slug: str, invite_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    invite = project.invites.get(pk=invite_id)

    if invite.status != "pending":
        return JsonResponse(
            {"ok": False, "errors": {"invite": ["Only pending invitations can be re-sent."]}},
            status=422,
        )

    try:
        with transaction.atomic():
            send_project_invitation_email(invite, request=request, is_resend=True)
            invite.mark_sent()
            invite.save(update_fields=["last_sent_at", "updated_at"])
            log_audit_event(
                project=project,
                actor=actor,
                event_type=AuditEventType.MEMBERSHIP_CHANGED,
                title=f"Re-sent invite to {invite.email}",
                description=f"Role: {invite.role}",
                metadata={"invite_id": invite.id, "email": invite.email, "role": invite.role, "action": "resend"},
            )
    except Exception:
        logger.exception("Failed to resend invitation email", extra={"project_slug": project.slug, "invite_id": invite.id})
        return JsonResponse(
            {"ok": False, "errors": {"email": ["Invitation email could not be delivered. Check email settings and try again."]}},
            status=502,
        )
    return {"ok": True, "invite": serialize_invite(invite)}


@router.post("/{slug}/memberships/invites/{invite_id}/revoke", auth=django_auth)
def revoke_invite(request, slug: str, invite_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    invite = project.invites.get(pk=invite_id)

    if invite.status != "pending":
        return JsonResponse(
            {"ok": False, "errors": {"invite": ["Only pending invitations can be revoked."]}},
            status=422,
        )

    invite.revoked_at = timezone.now()
    invite.save(update_fields=["revoked_at", "updated_at"])
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.MEMBERSHIP_CHANGED,
        title=f"Revoked invite for {invite.email}",
        description=f"Role: {invite.role}",
        metadata={"invite_id": invite.id, "email": invite.email, "role": invite.role, "action": "revoke"},
    )
    return {"ok": True, "invite": serialize_invite(invite)}


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
