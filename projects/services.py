from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from alignment.services import (
    build_workspace_entries,
    build_workspace_stream_items,
    compute_dashboard_metrics,
    normalize_workspace_stream_filter,
    workspace_concern_chat_prompt,
)
from projects.demo import DEMO_PROJECT_SLUG, DEMO_USERNAMES, ensure_demo_workspace
from projects.models import MembershipRole, Organization, Project, ProjectMembership
from specs.models import ConcernStatus, ConsistencyIssueStatus
from specs.services import (
    bootstrap_spec_document,
    capture_project_revision,
    compare_section_revisions,
    ensure_spec_document,
    section_summaries,
    section_title_for_ref,
)
from specs.concerns import ordered_concerns, render_proposal_change_diff

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
            f"{lead} This workspace keeps spec sections, decisions, assumptions, and delivery intent "
            f"for {project_name} aligned from the first draft onward."
        )
    return (
        f"A structured workspace for refining the {project_name} spec, decisions, "
        "assumptions, and delivery plan."
    )


def _summary_detail(summary: str, tagline: str) -> str:
    normalized_summary = (summary or "").strip()
    normalized_tagline = (tagline or "").strip()
    if not normalized_tagline or not normalized_summary.startswith(normalized_tagline):
        return normalized_summary
    detail = normalized_summary[len(normalized_tagline):].lstrip()
    if detail.startswith("."):
        detail = detail[1:].lstrip()
    return detail


def _compose_summary(tagline: str, detail: str) -> str:
    normalized_tagline = (tagline or "").strip()
    normalized_detail = (detail or "").strip()
    if not normalized_tagline:
        return normalized_detail
    lead = normalized_tagline if normalized_tagline.endswith((".", "!", "?")) else f"{normalized_tagline}."
    if not normalized_detail:
        return lead
    return f"{lead} {normalized_detail}"


def _default_summary_detail(project_name: str, tagline: str) -> str:
    return _summary_detail(_default_summary(project_name, tagline), tagline)


def split_project_summary(project) -> tuple[str, str]:
    tagline = (project.tagline or "").strip()
    summary = (project.summary or "").strip()
    if not tagline:
        return "", summary
    return tagline, _summary_detail(summary, tagline)


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
    bootstrap_spec_document(project)
    capture_project_revision(
        project=project,
        title="Initial workspace created",
        summary="Seeded the first single-spec workspace scaffold from the project directory.",
        actor=actor,
    )
    return project


def update_project_identity(
    *,
    project: Project,
    project_name: str,
    tagline: str,
):
    resolved_project_name = (project_name or "").strip()
    resolved_tagline = (tagline or "").strip() or _default_tagline(resolved_project_name)

    current_tagline, current_detail = split_project_summary(project)
    current_effective_tagline = current_tagline or _default_tagline(project.name)
    current_default_detail = _default_summary_detail(project.name, current_effective_tagline)

    next_detail = current_detail
    if not next_detail or next_detail == current_default_detail:
        next_detail = _default_summary_detail(resolved_project_name, resolved_tagline)

    project.name = resolved_project_name
    project.tagline = resolved_tagline
    project.summary = _compose_summary(resolved_tagline, next_detail)
    project.last_activity_at = timezone.now()
    project.save(update_fields=["name", "tagline", "summary", "last_activity_at", "updated_at"])
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
    memberships = list(project.memberships.select_related("user").order_by("-is_active", "created_at"))
    return {
        "project": project,
        "active_item": active_item,
        "navigation_items": navigation_for_project(project),
        "memberships": memberships,
        "header_variant": "project-toolbar",
        "header_memberships": [membership for membership in memberships if membership.is_active][:2],
        "active_members_count": sum(1 for membership in memberships if membership.is_active),
        "unresolved_count": metrics["unresolved_total"],
        "status_label": project.status_label,
        "dashboard_metrics": metrics,
        "latest_concern_run": project.concern_runs.first(),
    }


def project_directory_issue_summary(project):
    severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    active_concerns = [
        concern
        for concern in project.concerns.all()
        if concern.status in {ConcernStatus.OPEN, ConcernStatus.STALE}
    ]
    active_consistency_issues = [
        issue
        for issue in project.consistency_issues.all()
        if issue.status == ConsistencyIssueStatus.OPEN
    ]

    latest_issue_candidates = [
        {
            "title": concern.title,
            "summary": concern.summary,
            "type_label": concern.get_concern_type_display(),
            "status_label": concern.get_status_display(),
            "severity": concern.severity,
            "severity_label": concern.get_severity_display(),
            "sort_at": concern.last_seen_at or concern.detected_at or concern.updated_at,
            "severity_rank": severity_rank.get(concern.severity, 0),
        }
        for concern in active_concerns
    ]
    latest_issue_candidates.extend(
        {
            "title": issue.title,
            "summary": issue.summary,
            "type_label": "Consistency",
            "status_label": issue.get_status_display(),
            "severity": issue.severity,
            "severity_label": issue.get_severity_display(),
            "sort_at": issue.last_seen_at or issue.detected_at or issue.updated_at,
            "severity_rank": severity_rank.get(issue.severity, 0),
        }
        for issue in active_consistency_issues
    )
    latest_issue_candidates.sort(
        key=lambda item: (item["sort_at"], item["severity_rank"]),
        reverse=True,
    )
    latest_issue = latest_issue_candidates[0] if latest_issue_candidates else None

    return {
        "active_count": len(active_concerns) + len(active_consistency_issues),
        "critical_count": sum(1 for item in latest_issue_candidates if item["severity"] == "critical"),
        "latest_issue": latest_issue,
    }


def workspace_context(
    project,
    active_concern_id: str | None = None,
    active_section_id: str | None = None,
    stream_filter: str | None = None,
):
    context = page_context(project, "workspace")
    active_stream_filter = normalize_workspace_stream_filter(stream_filter)
    workspace_tagline, workspace_summary_detail = split_project_summary(project)
    spec_document = ensure_spec_document(project)
    sections = section_summaries(project)
    active_section = next((section for section in sections if section["id"] == active_section_id), None)
    concerns = ordered_concerns(project)
    selected_concern = next((concern for concern in concerns if str(concern.id) == str(active_concern_id)), None)
    concern_lookup: dict[str, list] = {}
    for concern in concerns:
        for ref in concern.node_refs or []:
            section_id = ref.get("section_id", "")
            if section_id:
                concern_lookup.setdefault(section_id, []).append(concern)

    spec_sections = [
        {
            "section": section,
            "concerns": concern_lookup.get(section["id"], []),
            "is_selected": bool(
                selected_concern
                and any(linked.id == selected_concern.id for linked in concern_lookup.get(section["id"], []))
            ),
            "is_active": section["id"] == active_section_id,
        }
        for section in sections
    ]
    selected_concern_posts = list(selected_concern.posts.select_related("author").all()) if selected_concern else []
    selected_concern_proposals = []
    if selected_concern:
        for proposal in selected_concern.proposals.prefetch_related("changes").all():
            selected_concern_proposals.append(
                {
                    "proposal": proposal,
                    "changes": [
                        {
                            "change": change,
                            "diff": render_proposal_change_diff(change),
                        }
                        for change in proposal.changes.all()
                    ],
                }
            )
    selected_section_ids = [
        ref.get("section_id", "")
        for ref in (selected_concern.node_refs if selected_concern else [])
        if ref.get("section_id")
    ]
    if not selected_section_ids and active_section:
        selected_section_ids = [active_section["id"]]
    workspace_stream_items = build_workspace_stream_items(
        project=project,
        concerns=concerns,
        selected_concern=selected_concern,
        selected_concern_posts=selected_concern_posts,
        selected_concern_proposals=selected_concern_proposals,
        stream_filter=active_stream_filter,
    )
    latest_project_revision = project.revisions.select_related("created_by", "source_post").order_by("-number").first()
    spec_last_updated_at = latest_project_revision.created_at if latest_project_revision else spec_document.updated_at
    spec_last_updated_by = ""
    if latest_project_revision:
        if latest_project_revision.created_by:
            spec_last_updated_by = latest_project_revision.created_by.display_name
        elif latest_project_revision.source_post:
            spec_last_updated_by = latest_project_revision.source_post.actor_name
    context.update(
        {
            "page_title": "Workspace",
            "page_breadcrumb_label": "Workspace",
            "header_hide_project_identity": True,
            "spec_document": spec_document,
            "sections": sections,
            "spec_sections": spec_sections,
            "assumptions": list(project.assumptions.select_related("created_by", "validated_by")),
            "concerns": concerns,
            "selected_concern": selected_concern,
            "selected_section_ids": selected_section_ids,
            "active_section": active_section,
            "selected_concern_posts": selected_concern_posts,
            "selected_concern_proposals": selected_concern_proposals,
            "activity_entries": build_workspace_entries(project),
            "workspace_stream_items": workspace_stream_items,
            "activity_posts": list(project.stream_posts.filter(concern__isnull=True).order_by("-created_at")[:8]),
            "workspace_tagline": workspace_tagline,
            "workspace_summary_detail": workspace_summary_detail,
            "active_stream_filter": active_stream_filter,
            "stream_filter_options": [
                {"value": "all", "label": "All", "icon": ""},
                {
                    "value": "decisions",
                    "label": "Decisions",
                    "icon": "lucide:check-circle-2",
                    "icon_class": "text-brand-decision",
                },
                {
                    "value": "open",
                    "label": "Open",
                    "icon": "lucide:alert-circle",
                    "icon_class": "text-brand-warning",
                },
            ],
            "selected_concern_chat_prompt": workspace_concern_chat_prompt(selected_concern) if selected_concern else "",
            "spec_last_updated_at": spec_last_updated_at,
            "spec_last_updated_by": spec_last_updated_by,
        }
    )
    return context


def dashboard_context(project):
    context = page_context(project, "team")
    context.update(
        {
            "sections": section_summaries(project),
            "concerns": ordered_concerns(project)[:8],
            "decisions": list(project.decisions.all()[:4]),
        }
    )
    return context


def decisions_context(project):
    context = page_context(project, "decisions")
    decisions = list(
        project.decisions.select_related("proposed_by", "supersedes").prefetch_related(
            "approvals__approver"
        )
    )
    for decision in decisions:
        decision.related_label = section_title_for_ref(project, decision.primary_ref)
    context["decisions"] = decisions
    return context


def history_context(project, active_section_id: str | None = None):
    context = page_context(project, "history")
    project_revisions = list(project.revisions.order_by("number"))
    left_project_revision = project_revisions[-2] if len(project_revisions) > 1 else (project_revisions[-1] if project_revisions else None)
    right_project_revision = project_revisions[-1] if project_revisions else None

    spec_document = ensure_spec_document(project)
    sections = section_summaries(project)
    active_section = next((section for section in sections if section["id"] == active_section_id), sections[0] if sections else None)
    spec_revisions = list(spec_document.revisions.order_by("number"))
    left_spec_revision = spec_revisions[-2] if len(spec_revisions) > 1 else (spec_revisions[-1] if spec_revisions else None)
    right_spec_revision = spec_revisions[-1] if spec_revisions else None
    context.update(
        {
            "project_revisions": project_revisions[::-1],
            "left_project_revision": left_project_revision,
            "right_project_revision": right_project_revision,
            "sections": sections,
            "active_section": active_section,
            "spec_revisions": spec_revisions[::-1],
            "left_spec_revision": left_spec_revision,
            "right_spec_revision": right_spec_revision,
            "section_diff": (
                compare_section_revisions(left_spec_revision, right_spec_revision, active_section["id"])
                if left_spec_revision and right_spec_revision and active_section
                else None
            ),
        }
    )
    return context


def handoff_context(project):
    context = page_context(project, "handoff")
    context.update(
        {
            "sections": section_summaries(project),
            "exports": list(project.exports.select_related("generated_by").all()),
            "share_members": [membership.user for membership in project.memberships.select_related("user")[:2]],
        }
    )
    return context


def assumptions_context(project):
    context = page_context(project, "assumptions")
    assumptions = list(project.assumptions.select_related("created_by", "validated_by"))
    for assumption in assumptions:
        assumption.related_label = section_title_for_ref(project, assumption.primary_ref)
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
