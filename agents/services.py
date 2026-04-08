from django.utils import timezone

from agents.models import AgentSuggestionStatus
from specs.models import AuditEventType
from specs.services import (
    log_audit_event,
    section_markdown_for_ref,
    section_title_for_ref,
    update_spec_section,
)
from specs.spec_document import markdown_to_blocks, strip_redundant_section_heading


def apply_suggestion(suggestion, actor):
    payload = suggestion.payload or {}
    primary_ref = suggestion.primary_ref or {}
    project_revision = None
    section_id = primary_ref.get("section_id", "")
    if section_id:
        proposed_body = payload.get("body_replace")
        if proposed_body is None and payload.get("body_append"):
            existing_body = section_markdown_for_ref(suggestion.project, primary_ref)
            proposed_body = f"{existing_body}\n\n{payload['body_append']}".strip()
        effective_title = (payload.get("title") or "").strip() or section_title_for_ref(suggestion.project, primary_ref)
        if proposed_body is not None and effective_title:
            proposed_body = strip_redundant_section_heading(proposed_body, effective_title)
        content_blocks = markdown_to_blocks(proposed_body or "") if proposed_body is not None else None
        project_revision = update_spec_section(
            project=suggestion.project,
            section_id=section_id,
            actor=actor,
            title=payload.get("title"),
            status=payload.get("status"),
            content_json=content_blocks,
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
            "target": primary_ref.get("section_id", ""),
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
