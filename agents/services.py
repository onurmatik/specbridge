from django.utils import timezone

from agents.models import AgentSuggestionStatus
from specs.models import AuditEventType
from specs.services import capture_document_revision, capture_project_revision, log_audit_event


def apply_suggestion(suggestion, actor):
    target = suggestion.related_document
    payload = suggestion.payload or {}
    project_revision = None
    if target:
        if payload.get("title"):
            target.title = payload["title"]
        if payload.get("body_replace") is not None:
            target.body = payload["body_replace"]
        if payload.get("body_append"):
            target.body = f"{target.body}\n\n{payload['body_append']}".strip()
        if payload.get("status"):
            target.status = payload["status"]
        target.save()
        project_revision = capture_project_revision(
            project=suggestion.project,
            title=f"Agent suggestion applied: {suggestion.title}",
            summary=suggestion.summary,
            actor=actor,
            source_agent=suggestion,
            source_post=suggestion.source_post,
        )
        capture_document_revision(
            document=target,
            title=f"Agent suggestion applied: {suggestion.title}",
            summary=suggestion.summary,
            actor=actor,
            project_revision=project_revision,
        )

    suggestion.status = AgentSuggestionStatus.APPLIED
    suggestion.applied_by = actor
    suggestion.acted_at = timezone.now()
    suggestion.save(update_fields=["status", "applied_by", "acted_at", "updated_at"])
    log_audit_event(
        project=suggestion.project,
        actor=actor,
        event_type=AuditEventType.AGENT_APPLIED,
        title=f"Applied agent suggestion: {suggestion.title}",
        description=suggestion.summary,
        source_agent=suggestion,
        source_post=suggestion.source_post,
        project_revision=project_revision,
        metadata={
            "suggestion_id": suggestion.id,
            "target": suggestion.related_document.slug if suggestion.related_document else "",
        },
    )
    return suggestion


def dismiss_suggestion(suggestion, actor):
    suggestion.status = AgentSuggestionStatus.DISMISSED
    suggestion.dismissed_by = actor
    suggestion.acted_at = timezone.now()
    suggestion.save(update_fields=["status", "dismissed_by", "acted_at", "updated_at"])
    log_audit_event(
        project=suggestion.project,
        actor=actor,
        event_type=AuditEventType.AGENT_DISMISSED,
        title=f"Dismissed agent suggestion: {suggestion.title}",
        description=suggestion.summary,
        source_agent=suggestion,
        source_post=suggestion.source_post,
        metadata={"suggestion_id": suggestion.id},
    )
    return suggestion
