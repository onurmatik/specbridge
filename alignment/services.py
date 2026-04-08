from __future__ import annotations

from collections import Counter

from django.utils import timezone

from alignment.models import DecisionStatus, IssueStatus, StreamAttachment, StreamPostKind
from specs.models import (
    AuditEventType,
    ConcernProposalStatus,
    ConcernStatus,
    ConcernType,
    DocumentStatus,
)
from specs.services import (
    capture_project_revision,
    ensure_spec_document,
    log_audit_event,
    section_summaries,
)
from specs.spec_document import update_section_content


def build_workspace_entries(project):
    entries = [
        {
            "kind": "post",
            "created_at": post.created_at,
            "post": post,
        }
        for post in project.stream_posts.filter(concern__isnull=True).all()
    ]
    entries.extend(
        {
            "kind": "decision",
            "created_at": decision.created_at,
            "decision": decision,
        }
        for decision in project.decisions.exclude(status=DecisionStatus.PENDING)
    )
    return sorted(entries, key=lambda item: item["created_at"])


VALID_WORKSPACE_STREAM_FILTERS = {"all", "decisions", "open", "files"}


def normalize_workspace_stream_filter(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    return normalized if normalized in VALID_WORKSPACE_STREAM_FILTERS else "all"


def workspace_concern_chat_prompt(concern) -> str:
    prompt = (
        f'Help me resolve the concern "{concern.title}". '
        f"Current issue: {concern.summary}"
    )
    recommendation = (concern.recommendation or "").strip()
    if recommendation:
        prompt = f"{prompt} Suggested next step: {recommendation}"
    return prompt


def _prefetched_related_list(instance, relation_name: str) -> list:
    cache = getattr(instance, "_prefetched_objects_cache", {})
    if relation_name in cache:
        return list(cache[relation_name])
    return list(getattr(instance, relation_name).all())


def _build_workspace_post_item(post, *, concern=None):
    author = getattr(post, "author", None)
    avatar_url = author.avatar_url if author else ""
    is_agent = post.kind == StreamPostKind.AGENT
    attachments = _prefetched_related_list(post, "attachments")
    has_body = bool((post.body or "").strip())
    return {
        "kind": "agent_notice" if is_agent else "message",
        "created_at": post.created_at,
        "post": post,
        "concern": concern,
        "avatar_url": avatar_url,
        "attachments": attachments,
        "has_body": has_body,
        "is_file_only": bool(attachments and not has_body),
        "is_focus_thread": bool(concern),
        "is_open_related": bool(concern and concern.status in {ConcernStatus.OPEN, ConcernStatus.STALE}),
    }


def _build_workspace_decision_item(decision):
    actor_name = (
        decision.proposed_by.display_name
        if getattr(decision, "proposed_by", None)
        else (decision.source_post.actor_name if getattr(decision, "source_post", None) else "Team")
    )
    return {
        "kind": "decision",
        "created_at": decision.created_at,
        "decision": decision,
        "actor_name": actor_name,
        "is_open_related": False,
    }


def _build_workspace_concern_item(concern, *, is_selected=False):
    return {
        "kind": "concern",
        "created_at": concern.detected_at or concern.created_at,
        "concern": concern,
        "is_selected": is_selected,
        "chat_prompt": workspace_concern_chat_prompt(concern),
        "is_open_related": concern.status in {ConcernStatus.OPEN, ConcernStatus.STALE},
    }


def _build_workspace_proposal_item(bundle, *, concern):
    proposal = bundle["proposal"]
    return {
        "kind": "proposal",
        "created_at": proposal.created_at,
        "proposal": proposal,
        "changes": bundle["changes"],
        "concern": concern,
        "is_open_related": (
            concern.status in {ConcernStatus.OPEN, ConcernStatus.STALE}
            and proposal.status in {ConcernProposalStatus.OPEN, ConcernProposalStatus.PARTIALLY_APPLIED}
        ),
    }


def _build_workspace_attachment_item(attachment):
    post = attachment.post
    author = getattr(post, "author", None)
    concern = getattr(post, "concern", None)
    return {
        "kind": "file",
        "created_at": attachment.created_at,
        "attachment": attachment,
        "post": post,
        "concern": concern,
        "avatar_url": author.avatar_url if author else "",
        "is_open_related": bool(concern and concern.status in {ConcernStatus.OPEN, ConcernStatus.STALE}),
    }


def build_workspace_stream_items(
    *,
    project,
    concerns,
    selected_concern=None,
    selected_concern_posts=None,
    selected_concern_proposals=None,
    stream_filter="all",
):
    normalized_filter = normalize_workspace_stream_filter(stream_filter)
    if normalized_filter == "files":
        attachments = list(
            StreamAttachment.objects.select_related("post__author", "post__concern")
            .filter(project=project)
            .order_by("created_at")
        )
        return [_build_workspace_attachment_item(attachment) for attachment in attachments]

    items = []
    top_level_posts = list(
        project.stream_posts.select_related("author")
        .prefetch_related("attachments")
        .filter(concern__isnull=True)
    )
    approved_decisions = list(
        project.decisions.select_related("proposed_by", "source_post").exclude(status=DecisionStatus.PENDING)
    )

    items.extend(_build_workspace_post_item(post) for post in top_level_posts)
    items.extend(_build_workspace_decision_item(decision) for decision in approved_decisions)
    items.extend(
        _build_workspace_concern_item(concern, is_selected=bool(selected_concern and concern.id == selected_concern.id))
        for concern in concerns
        if not (selected_concern and concern.id == selected_concern.id)
    )

    if selected_concern:
        items.extend(
            _build_workspace_post_item(post, concern=selected_concern)
            for post in (selected_concern_posts or [])
        )
        items.extend(
            _build_workspace_proposal_item(bundle, concern=selected_concern)
            for bundle in (selected_concern_proposals or [])
        )

    items.sort(key=lambda item: item["created_at"])

    if normalized_filter == "decisions":
        return [item for item in items if item["kind"] == "decision"]
    if normalized_filter == "open":
        return [item for item in items if item["is_open_related"]]
    return items


def compute_dashboard_metrics(project):
    sections = section_summaries(project)
    required_sections = [section for section in sections if section["required"]]
    aligned_count = sum(1 for section in sections if section["status"] == DocumentStatus.ALIGNED)
    iterating_count = sum(1 for section in sections if section["status"] == DocumentStatus.ITERATING)
    blocked_count = sum(1 for section in sections if section["status"] == DocumentStatus.BLOCKED)
    completeness = 0
    if required_sections:
        completeness = sum(1 for section in required_sections if section["body"].strip()) / len(required_sections)

    active_concerns = project.concerns.filter(status__in=[ConcernStatus.OPEN, ConcernStatus.STALE])
    critical_concerns = active_concerns.filter(severity="critical").count()
    open_questions = active_concerns.filter(concern_type=ConcernType.HUMAN_FLAG).count()
    open_blockers = active_concerns.filter(concern_type=ConcernType.IMPLEMENTABILITY).count()
    open_consistency_issues = active_concerns.filter(concern_type=ConcernType.CONSISTENCY).count()
    implementability_concerns = active_concerns.filter(concern_type=ConcernType.IMPLEMENTABILITY).count()
    usability_concerns = active_concerns.filter(concern_type=ConcernType.USABILITY).count()
    business_viability_concerns = active_concerns.filter(concern_type=ConcernType.BUSINESS_VIABILITY).count()
    resolved_questions = project.concerns.filter(
        concern_type=ConcernType.HUMAN_FLAG,
        status=ConcernStatus.RESOLVED,
    ).count()
    resolved_blockers = project.concerns.filter(
        concern_type=ConcernType.IMPLEMENTABILITY,
        status=ConcernStatus.RESOLVED,
    ).count()
    penalty = open_blockers * 8 + critical_concerns * 15 + open_questions * 5 + open_consistency_issues * 6
    base_score = int(completeness * 80) + min(resolved_questions + resolved_blockers, 20)
    maturity_score = max(min(base_score - penalty, 100), 0)

    week_ago = timezone.now() - timezone.timedelta(days=7)
    approved_in_week = project.decisions.filter(
        status__in=[DecisionStatus.APPROVED, DecisionStatus.IMPLEMENTED],
        updated_at__gte=week_ago,
    ).count()
    decision_velocity = round(approved_in_week / 7, 1)

    alignment = round((aligned_count / len(sections)) * 100) if sections else 0
    by_status = Counter(section["status"] for section in sections)
    return {
        "alignment_percentage": alignment,
        "maturity_score": maturity_score,
        "decision_velocity": decision_velocity,
        "critical_blockers": critical_concerns,
        "open_questions": open_questions,
        "resolved_questions": resolved_questions,
        "resolved_blockers": resolved_blockers,
        "open_consistency_issues": open_consistency_issues,
        "open_concerns": active_concerns.count(),
        "implementability_concerns": implementability_concerns,
        "usability_concerns": usability_concerns,
        "business_viability_concerns": business_viability_concerns,
        "document_status_counts": {
            "aligned": by_status.get(DocumentStatus.ALIGNED, 0),
            "iterating": by_status.get(DocumentStatus.ITERATING, 0),
            "blocked": by_status.get(DocumentStatus.BLOCKED, 0),
        },
        "active_members": project.memberships.filter(is_active=True).count(),
        "unresolved_total": active_concerns.count(),
        "iterating_count": iterating_count,
        "blocked_count": blocked_count,
    }


def approve_decision(decision, actor):
    approval, _ = decision.approvals.update_or_create(
        approver=actor,
        defaults={"approved": True, "note": "Approved from workspace"},
    )
    decision.status = DecisionStatus.APPROVED
    decision.approved_at = timezone.now()
    decision.save(update_fields=["status", "approved_at", "updated_at"])
    primary_ref = decision.primary_ref or {}
    if primary_ref.get("section_id"):
        spec_document = ensure_spec_document(decision.project)
        next_content, _, changed = update_section_content(
            spec_document.content_json,
            primary_ref["section_id"],
            status=DocumentStatus.ALIGNED,
        )
        if changed:
            spec_document.content_json = next_content
            spec_document.save(update_fields=["content_json", "updated_at"])
    revision = capture_project_revision(
        project=decision.project,
        title=f"Decision approved: {decision.title}",
        summary=decision.summary,
        actor=actor,
        source_decision=decision,
        source_post=decision.source_post,
    )
    log_audit_event(
        project=decision.project,
        actor=actor,
        event_type=AuditEventType.DECISION_APPROVED,
        title=f"Approved {decision.title}",
        description=decision.summary,
        source_decision=decision,
        source_post=decision.source_post,
        project_revision=revision,
        metadata={"decision_id": decision.id},
    )
    return approval


def reject_decision(decision, actor, note="Rejected from workspace"):
    decision.approvals.update_or_create(
        approver=actor,
        defaults={"approved": False, "note": note},
    )
    decision.status = DecisionStatus.REJECTED
    decision.save(update_fields=["status", "updated_at"])
    log_audit_event(
        project=decision.project,
        actor=actor,
        event_type=AuditEventType.DECISION_REJECTED,
        title=f"Rejected {decision.title}",
        description=note,
        source_decision=decision,
        source_post=decision.source_post,
        metadata={"decision_id": decision.id},
    )
    return decision


def mark_decision_implemented(decision, actor):
    decision.status = DecisionStatus.IMPLEMENTED
    decision.implementation_progress = 100
    decision.implemented_at = timezone.now()
    decision.save(update_fields=["status", "implementation_progress", "implemented_at", "updated_at"])
    revision = capture_project_revision(
        project=decision.project,
        title=f"Decision implemented: {decision.title}",
        summary=decision.summary,
        actor=actor,
        source_decision=decision,
        source_post=decision.source_post,
    )
    log_audit_event(
        project=decision.project,
        actor=actor,
        event_type=AuditEventType.DECISION_IMPLEMENTED,
        title=f"Implemented {decision.title}",
        description=decision.summary,
        source_decision=decision,
        source_post=decision.source_post,
        project_revision=revision,
        metadata={"decision_id": decision.id},
    )
    return decision


def resolve_issue(issue, actor):
    issue.status = IssueStatus.RESOLVED
    issue.resolved_by = actor
    issue.resolved_at = timezone.now()
    issue.save(update_fields=["status", "resolved_by", "resolved_at", "updated_at"])
    return issue


def reopen_issue(issue):
    issue.status = IssueStatus.REOPENED
    issue.resolved_at = None
    issue.save(update_fields=["status", "resolved_at", "updated_at"])
    return issue
