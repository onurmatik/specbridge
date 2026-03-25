from __future__ import annotations

from collections import Counter

from django.db.models import Count, Q
from django.utils import timezone

from alignment.models import DecisionStatus, IssueStatus
from specs.models import AuditEventType, SectionStatus
from specs.services import capture_version, log_audit_event


def build_workspace_entries(project):
    entries = [
        {
            "kind": "post",
            "created_at": post.created_at,
            "post": post,
        }
        for post in project.stream_posts.all()
    ]
    entries.extend(
        {
            "kind": "agent",
            "created_at": suggestion.created_at,
            "suggestion": suggestion,
        }
        for suggestion in project.agent_suggestions.all()
    )
    entries.extend(
        {
            "kind": "decision",
            "created_at": decision.created_at,
            "decision": decision,
        }
        for decision in project.decisions.exclude(status=DecisionStatus.PENDING)
    )
    return sorted(entries, key=lambda item: item["created_at"])


def compute_dashboard_metrics(project):
    sections = list(project.sections.all())
    required_sections = [section for section in sections if section.is_required]
    aligned_count = sum(1 for section in sections if section.status == SectionStatus.ALIGNED)
    iterating_count = sum(1 for section in sections if section.status == SectionStatus.ITERATING)
    blocked_count = sum(1 for section in sections if section.status == SectionStatus.BLOCKED)
    completeness = 0
    if required_sections:
        completeness = sum(1 for section in required_sections if section.body.strip()) / len(required_sections)

    open_questions = project.questions.filter(status__in=[IssueStatus.OPEN, IssueStatus.REOPENED]).count()
    open_blockers = project.blockers.filter(status__in=[IssueStatus.OPEN, IssueStatus.REOPENED]).count()
    critical_blockers = project.blockers.filter(
        status__in=[IssueStatus.OPEN, IssueStatus.REOPENED],
        severity="critical",
    ).count()
    resolved_questions = project.questions.filter(status=IssueStatus.RESOLVED).count()
    resolved_blockers = project.blockers.filter(status=IssueStatus.RESOLVED).count()
    penalty = open_blockers * 8 + critical_blockers * 15 + open_questions * 5
    base_score = int(completeness * 80) + min(resolved_questions + resolved_blockers, 20)
    maturity_score = max(min(base_score - penalty, 100), 0)

    week_ago = timezone.now() - timezone.timedelta(days=7)
    approved_in_week = project.decisions.filter(
        status__in=[DecisionStatus.APPROVED, DecisionStatus.IMPLEMENTED],
        updated_at__gte=week_ago,
    ).count()
    decision_velocity = round(approved_in_week / 7, 1)

    alignment = round((aligned_count / len(sections)) * 100) if sections else 0
    by_status = Counter(section.status for section in sections)
    return {
        "alignment_percentage": alignment,
        "maturity_score": maturity_score,
        "decision_velocity": decision_velocity,
        "critical_blockers": critical_blockers,
        "open_questions": open_questions,
        "resolved_questions": resolved_questions,
        "resolved_blockers": resolved_blockers,
        "section_status_counts": {
            "aligned": by_status.get(SectionStatus.ALIGNED, 0),
            "iterating": by_status.get(SectionStatus.ITERATING, 0),
            "blocked": by_status.get(SectionStatus.BLOCKED, 0),
        },
        "active_members": project.memberships.filter(is_active=True).count(),
        "unresolved_total": open_questions + open_blockers,
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
    if decision.related_section_key:
        section = decision.project.sections.filter(key=decision.related_section_key).first()
        if section:
            section.status = SectionStatus.ALIGNED
            section.save(update_fields=["status", "updated_at"])
    version = capture_version(
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
        spec_version=version,
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
    version = capture_version(
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
        spec_version=version,
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
