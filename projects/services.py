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
from specs.models import SectionStatus, SpecSection
from specs.services import capture_version
from specs.services import compare_versions

DEFAULT_PROJECT_STATUS_LABEL = "Aligning"

PROJECT_BOOTSTRAP_SECTIONS = (
    {
        "key": "problem-goals",
        "title": "Problem & Goals",
        "summary": "Frame the problem, the business outcome, and the success signal.",
        "body_template": (
            "{project_name} starts with a shared articulation of the problem.\n\n"
            "- Customer pain:\n"
            "- Business objective:\n"
            "- Success metric:\n\n"
            "Working direction: {tagline}"
        ),
    },
    {
        "key": "proposed-solution",
        "title": "Proposed Solution",
        "summary": "Describe the core product or workflow change this project is driving.",
        "body_template": (
            "Capture the proposed solution for {project_name} in concrete terms.\n\n"
            "- Scope for the first release:\n"
            "- Key user flow changes:\n"
            "- What remains out of scope:\n\n"
            "Current summary: {summary}"
        ),
    },
    {
        "key": "technical-implementation",
        "title": "Technical Implementation",
        "summary": "Outline architecture, rollout constraints, and delivery dependencies.",
        "body_template": (
            "Use this section to align engineering on implementation shape.\n\n"
            "- Systems impacted:\n"
            "- Rollout / migration plan:\n"
            "- Observability and risk checks:"
        ),
    },
    {
        "key": "ux-interfaces",
        "title": "UX & Interfaces",
        "summary": "Track interface changes, content requirements, and edge-case behavior.",
        "body_template": (
            "Document the interface implications for {project_name}.\n\n"
            "- Entry points:\n"
            "- Empty / loading / failure states:\n"
            "- Collaboration or approval touchpoints:"
        ),
    },
    {
        "key": "risks-open-questions",
        "title": "Risks & Open Questions",
        "summary": "Keep unknowns, dependencies, and launch blockers visible from day one.",
        "body_template": (
            "List the highest-risk assumptions and unresolved questions before build.\n\n"
            "- Top dependency:\n"
            "- Hardest open question:\n"
            "- What would block launch?"
        ),
    },
)


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
        return (
            f"{tagline} This workspace keeps the spec, decisions, assumptions, and delivery plan "
            f"for {project_name} aligned from the first draft onward."
        )
    return (
        f"A structured workspace for refining the {project_name} specification, decisions, "
        "assumptions, and delivery plan."
    )


def _bootstrap_sections(project, tagline: str, summary: str) -> None:
    SpecSection.objects.bulk_create(
        [
            SpecSection(
                project=project,
                key=section["key"],
                title=section["title"],
                summary=section["summary"],
                body=section["body_template"].format(
                    project_name=project.name,
                    tagline=tagline,
                    summary=summary,
                ),
                status=SectionStatus.ITERATING,
                order=index,
            )
            for index, section in enumerate(PROJECT_BOOTSTRAP_SECTIONS, start=1)
        ]
    )


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
    _bootstrap_sections(project, resolved_tagline, summary)
    capture_version(
        project=project,
        title="Initial workspace created",
        summary="Seeded the first spec scaffold from the project directory.",
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
    }


def workspace_context(project):
    context = page_context(project, "workspace")
    context.update(
        {
            "stream_entries": build_workspace_entries(project),
            "sections": list(project.sections.prefetch_related("assumptions")),
            "questions": list(project.questions.all()),
            "assumptions": list(project.assumptions.select_related("section")),
            "agent_suggestions": list(project.agent_suggestions.all()),
        }
    )
    return context


def dashboard_context(project):
    context = page_context(project, "team")
    context.update(
        {
            "sections": list(project.sections.all()),
            "questions": list(project.questions.all()),
            "blockers": list(project.blockers.all()),
            "decisions": list(project.decisions.all()[:4]),
        }
    )
    return context


def decisions_context(project):
    context = page_context(project, "decisions")
    context["decisions"] = list(
        project.decisions.select_related("proposed_by", "supersedes").prefetch_related("approvals__approver")
    )
    return context


def history_context(project):
    context = page_context(project, "history")
    versions = list(project.versions.order_by("number"))
    left_version = versions[-2] if len(versions) > 1 else versions[-1]
    right_version = versions[-1]
    context.update(
        {
            "versions": versions[::-1],
            "left_version": left_version,
            "right_version": right_version,
            "diff_rows": compare_versions(left_version, right_version),
        }
    )
    return context


def handoff_context(project):
    context = page_context(project, "handoff")
    context.update(
        {
            "sections": list(project.sections.all()),
            "exports": list(project.exports.select_related("generated_by").all()),
            "share_members": [membership.user for membership in project.memberships.select_related("user")[:2]],
        }
    )
    return context


def assumptions_context(project):
    context = page_context(project, "assumptions")
    assumptions = list(project.assumptions.select_related("section", "created_by", "validated_by"))
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
