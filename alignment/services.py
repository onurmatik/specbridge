from __future__ import annotations

from collections import Counter

from django.utils import timezone

from alignment.models import DecisionStatus, IssueStatus
from specs.models import AuditEventType, ConcernStatus, ConcernType, DocumentStatus
from specs.services import capture_project_revision, log_audit_event


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
        for decision in project.decisions.select_related("related_document").exclude(status=DecisionStatus.PENDING)
    )
    return sorted(entries, key=lambda item: item["created_at"])


def compute_dashboard_metrics(project):
    documents = list(project.documents.all())
    required_documents = [document for document in documents if document.is_required]
    aligned_count = sum(1 for document in documents if document.status == DocumentStatus.ALIGNED)
    iterating_count = sum(1 for document in documents if document.status == DocumentStatus.ITERATING)
    blocked_count = sum(1 for document in documents if document.status == DocumentStatus.BLOCKED)
    completeness = 0
    if required_documents:
        completeness = sum(1 for document in required_documents if document.body.strip()) / len(required_documents)

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

    alignment = round((aligned_count / len(documents)) * 100) if documents else 0
    by_status = Counter(document.status for document in documents)
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
    if decision.related_document:
        decision.related_document.status = DocumentStatus.ALIGNED
        decision.related_document.save(update_fields=["status", "updated_at"])
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
