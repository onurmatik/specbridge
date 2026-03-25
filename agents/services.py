from django.utils import timezone

from agents.models import AgentSuggestionStatus
from specs.models import AuditEventType
from specs.services import capture_version, log_audit_event


def apply_suggestion(suggestion, actor):
    target = suggestion.project.sections.filter(key=suggestion.related_section_key).first()
    payload = suggestion.payload or {}
    if target:
        if payload.get("summary"):
            target.summary = payload["summary"]
        if payload.get("body_append"):
            target.body = f"{target.body}\n\n{payload['body_append']}".strip()
        if payload.get("status"):
            target.status = payload["status"]
        target.save()
    suggestion.status = AgentSuggestionStatus.APPLIED
    suggestion.applied_by = actor
    suggestion.acted_at = timezone.now()
    suggestion.save(update_fields=["status", "applied_by", "acted_at", "updated_at"])
    version = capture_version(
        project=suggestion.project,
        title=f"Agent suggestion applied: {suggestion.title}",
        summary=suggestion.summary,
        actor=actor,
        source_agent=suggestion,
        source_post=suggestion.source_post,
    )
    log_audit_event(
        project=suggestion.project,
        actor=actor,
        event_type=AuditEventType.AGENT_APPLIED,
        title=f"Applied agent suggestion: {suggestion.title}",
        description=suggestion.summary,
        source_agent=suggestion,
        source_post=suggestion.source_post,
        spec_version=version,
        metadata={"suggestion_id": suggestion.id, "target": suggestion.related_section_key},
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
