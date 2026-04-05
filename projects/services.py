from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from alignment.services import build_workspace_entries, compute_dashboard_metrics
from projects.demo import DEMO_PROJECT_SLUG, DEMO_USERNAMES, ensure_demo_workspace
from projects.models import MembershipRole, Organization, Project, ProjectMembership
from specs.services import (
    DOCUMENT_SUGGESTIONS,
    bootstrap_documents,
    capture_project_revision,
    compare_document_revisions,
)

DEFAULT_PROJECT_STATUS_LABEL = "Aligning"


def can_access_demo_project(user) -> bool:
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "username", "") in DEMO_USERNAMES
    )


def visible_projects_for_user(user):
    projects = Project.objects.select_related("organization")
    if user is not None and getattr(user, "is_authenticated", False):
        visible_projects = projects.filter(memberships__user=user, memberships__is_active=True)
        if not can_access_demo_project(user):
            visible_projects = visible_projects.exclude(slug=DEMO_PROJECT_SLUG)
        return visible_projects.distinct()

    ensure_demo_workspace()
    return projects.filter(slug=DEMO_PROJECT_SLUG)


def get_primary_project(user=None):
    return visible_projects_for_user(user).order_by("-last_activity_at", "-updated_at", "name").first()


def get_project_or_404(slug: str, user=None):
    try:
        return visible_projects_for_user(user).get(slug=slug)
    except Project.DoesNotExist as exc:
        raise Http404("Project not found") from exc


def resolve_actor(request, project):
    if not request.user.is_authenticated:
        raise PermissionDenied("Authentication required")
    return request.user


def _unique_project_slug(name: str) -> str:
    base_slug = slugify(name) or "project"
    slug = base_slug
    suffix = 2
    while Project.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def _creator_role(actor) -> str:
    normalized_title = (actor.title or "").lower()
    if "ceo" in normalized_title or "founder" in normalized_title:
        return MembershipRole.CEO
    if "design" in normalized_title:
        return MembershipRole.DESIGN
    if "eng" in normalized_title or "developer" in normalized_title:
        return MembershipRole.ENGINEERING
    return MembershipRole.PRODUCT


def _default_organization_name(actor) -> str:
    return f"{actor.display_name} Workspace"


def _default_tagline(project_name: str) -> str:
    return f"Collaborative workspace for shaping {project_name}."


def _default_summary(project_name: str, tagline: str) -> str:
    if tagline:
        lead = tagline if tagline.endswith((".", "!", "?")) else f"{tagline}."
        return (
            f"{lead} This workspace keeps documents, decisions, assumptions, and delivery intent "
            f"for {project_name} aligned from the first draft onward."
        )
    return (
        f"A structured workspace for refining the {project_name} documents, decisions, "
        "assumptions, and delivery plan."
    )


def split_project_summary(project) -> tuple[str, str]:
    tagline = (project.tagline or "").strip()
    summary = (project.summary or "").strip()
    if not tagline:
        return "", summary
    if summary.startswith(tagline):
        detail = summary[len(tagline):].lstrip()
        if detail.startswith("."):
            detail = detail[1:].lstrip()
        return tagline, detail
    return tagline, summary


@transaction.atomic
def create_project_workspace(
    *,
    actor,
    project_name: str,
    tagline: str,
):
    resolved_tagline = tagline or _default_tagline(project_name)
    summary = _default_summary(project_name, resolved_tagline)
    organization_name = _default_organization_name(actor)
    organization_slug = slugify(organization_name) or "workspace-org"
    organization, _ = Organization.objects.get_or_create(
        slug=organization_slug,
        defaults={"name": organization_name},
    )

    project = Project.objects.create(
        organization=organization,
        name=project_name,
        slug=_unique_project_slug(project_name),
        tagline=resolved_tagline,
        summary=summary,
        status_label=DEFAULT_PROJECT_STATUS_LABEL,
        created_by=actor,
        last_activity_at=timezone.now(),
    )
    ProjectMembership.objects.create(
        project=project,
        user=actor,
        role=_creator_role(actor),
        title=actor.title or "Workspace Owner",
    )
    bootstrap_documents(project)
    capture_project_revision(
        project=project,
        title="Initial workspace created",
        summary="Seeded the first multi-document workspace scaffold from the project directory.",
        actor=actor,
    )
    return project


def navigation_for_project(project):
    return [
        {"key": "projects", "label": "Projects", "icon": "lucide:folder-open", "url": reverse("project-directory")},
        {
            "key": "workspace",
            "label": "Workspace",
            "icon": "lucide:file-pen-line",
            "url": reverse("project-workspace", args=[project.slug]),
        },
        {
            "key": "team",
            "label": "Dashboard",
            "icon": "lucide:layout-dashboard",
            "url": reverse("project-dashboard", args=[project.slug]),
        },
        {
            "key": "decisions",
            "label": "Decisions",
            "icon": "lucide:gavel",
            "url": reverse("project-decisions", args=[project.slug]),
        },
        {
            "key": "history",
            "label": "History",
            "icon": "lucide:git-compare-arrows",
            "url": reverse("project-history", args=[project.slug]),
        },
        {
            "key": "handoff",
            "label": "Handoff",
            "icon": "lucide:send",
            "url": reverse("project-handoff", args=[project.slug]),
        },
        {
            "key": "assumptions",
            "label": "Assumptions",
            "icon": "lucide:flask-conical",
            "url": reverse("project-assumptions", args=[project.slug]),
        },
        {
            "key": "members",
            "label": "Members",
            "icon": "lucide:users",
            "url": reverse("project-members", args=[project.slug]),
        },
    ]


def page_context(project, active_item):
    metrics = compute_dashboard_metrics(project)
    memberships = list(project.memberships.select_related("user"))
    return {
        "project": project,
        "active_item": active_item,
        "navigation_items": navigation_for_project(project),
        "memberships": memberships,
        "active_members_count": sum(1 for membership in memberships if membership.is_active),
        "unresolved_count": metrics["unresolved_total"],
        "status_label": project.status_label,
        "dashboard_metrics": metrics,
        "latest_consistency_run": project.consistency_runs.first(),
    }


def workspace_context(project, active_document_slug: str | None = None):
    context = page_context(project, "workspace")
    workspace_tagline, workspace_summary_detail = split_project_summary(project)
    documents = list(project.documents.prefetch_related("assumptions"))
    active_document = next((doc for doc in documents if doc.slug == active_document_slug), documents[0] if documents else None)
    consistency_issues = list(project.consistency_issues.all()[:8])
    context.update(
        {
            "stream_entries": build_workspace_entries(project),
            "documents": documents,
            "active_document": active_document,
            "document_revisions": list(active_document.revisions.order_by("-number")[:5]) if active_document else [],
            "document_suggestions": DOCUMENT_SUGGESTIONS,
            "questions": list(project.questions.select_related("related_document")),
            "assumptions": list(project.assumptions.select_related("document")),
            "agent_suggestions": list(project.agent_suggestions.select_related("related_document")),
            "consistency_issues": consistency_issues,
            "workspace_tagline": workspace_tagline,
            "workspace_summary_detail": workspace_summary_detail,
        }
    )
    return context


def dashboard_context(project):
    context = page_context(project, "team")
    context.update(
        {
            "documents": list(project.documents.all()),
            "questions": list(project.questions.select_related("related_document").all()),
            "blockers": list(project.blockers.select_related("related_document").all()),
            "decisions": list(project.decisions.select_related("related_document").all()[:4]),
            "consistency_issues": list(project.consistency_issues.all()[:5]),
        }
    )
    return context


def decisions_context(project):
    context = page_context(project, "decisions")
    context["decisions"] = list(
        project.decisions.select_related("proposed_by", "supersedes", "related_document").prefetch_related(
            "approvals__approver"
        )
    )
    return context


def history_context(project, active_document_slug: str | None = None):
    context = page_context(project, "history")
    project_revisions = list(project.revisions.order_by("number"))
    left_project_revision = project_revisions[-2] if len(project_revisions) > 1 else (project_revisions[-1] if project_revisions else None)
    right_project_revision = project_revisions[-1] if project_revisions else None

    documents = list(project.documents.order_by("order", "created_at"))
    active_document = next((doc for doc in documents if doc.slug == active_document_slug), documents[0] if documents else None)
    document_revisions = list(active_document.revisions.order_by("number")) if active_document else []
    left_document_revision = (
        document_revisions[-2] if len(document_revisions) > 1 else (document_revisions[-1] if document_revisions else None)
    )
    right_document_revision = document_revisions[-1] if document_revisions else None
    context.update(
        {
            "project_revisions": project_revisions[::-1],
            "left_project_revision": left_project_revision,
            "right_project_revision": right_project_revision,
            "documents": documents,
            "active_document": active_document,
            "document_revisions": document_revisions[::-1],
            "left_document_revision": left_document_revision,
            "right_document_revision": right_document_revision,
            "document_diff": (
                compare_document_revisions(left_document_revision, right_document_revision)
                if left_document_revision and right_document_revision
                else None
            ),
        }
    )
    return context


def handoff_context(project):
    context = page_context(project, "handoff")
    context.update(
        {
            "documents": list(project.documents.all()),
            "exports": list(project.exports.select_related("generated_by").all()),
            "share_members": [membership.user for membership in project.memberships.select_related("user")[:2]],
        }
    )
    return context


def assumptions_context(project):
    context = page_context(project, "assumptions")
    assumptions = list(project.assumptions.select_related("document", "created_by", "validated_by"))
    context["assumptions"] = assumptions
    context["assumption_counts"] = {
        "open": sum(1 for assumption in assumptions if assumption.status == "open"),
        "validated": sum(1 for assumption in assumptions if assumption.status == "validated"),
        "invalidated": sum(1 for assumption in assumptions if assumption.status == "invalidated"),
    }
    return context


def members_context(project):
    context = page_context(project, "members")
    context["invites"] = list(project.invites.all())
    return context
