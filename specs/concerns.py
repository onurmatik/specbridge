from __future__ import annotations

import difflib
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from specs.models import (
    AuditEventType,
    ConcernProposal,
    ConcernProposalChange,
    ConcernProposalChangeStatus,
    ConcernProposalStatus,
    ConcernRaisedByKind,
    ConcernRun,
    ConcernRunStatus,
    ConcernSeverity,
    ConcernStatus,
    ConcernType,
    ProjectConcern,
)
from specs.services import (
    build_primary_ref_for_identifier,
    build_project_snapshot,
    ensure_spec_document,
    log_audit_event,
    update_spec_section,
)
from specs.spec_document import (
    blocks_to_markdown,
    collect_refs_from_text,
    find_section,
    markdown_to_blocks,
    normalized_spec_content,
    section_catalog,
    section_summary,
)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
AI_CONCERN_SCOPES = (
    ConcernType.CONSISTENCY,
    ConcernType.IMPLEMENTABILITY,
    ConcernType.USABILITY,
    ConcernType.BUSINESS_VIABILITY,
)

CONCERN_ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "concerns": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "concern_type": {"type": "string", "enum": list(AI_CONCERN_SCOPES)},
                    "fingerprint": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "recommendation": {"type": "string"},
                    "source_refs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "kind": {"type": "string"},
                                "identifier": {"type": "string"},
                                "label": {"type": "string"},
                            },
                            "required": ["kind", "identifier", "label"],
                        },
                    },
                },
                "required": [
                    "concern_type",
                    "fingerprint",
                    "title",
                    "summary",
                    "severity",
                    "recommendation",
                    "source_refs",
                ],
            },
        }
    },
    "required": ["concerns"],
}

CONCERN_REEVALUATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["open", "resolved"]},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "recommendation": {"type": "string"},
        "source_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string"},
                    "identifier": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["kind", "identifier", "label"],
            },
        },
    },
    "required": ["status", "title", "summary", "severity", "recommendation", "source_refs"],
}

CONCERN_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "proposed_body": {"type": "string"},
                },
                "required": ["section_id", "summary", "proposed_body"],
            },
        },
    },
    "required": ["summary", "changes"],
}


class ConcernError(Exception):
    pass


@dataclass
class ConcernAnalysisResult:
    provider: str
    model: str
    concerns: list[dict]


@dataclass
class ConcernReevaluationResult:
    provider: str
    model: str
    status: str
    title: str
    summary: str
    severity: str
    recommendation: str
    source_refs: list[dict]


@dataclass
class ConcernProposalResult:
    provider: str
    model: str
    summary: str
    changes: list[dict]


def _extract_output_text(response_payload: dict) -> str:
    output_text = response_payload.get("output_text")
    if output_text:
        return output_text

    fragments: list[str] = []
    for output_item in response_payload.get("output", []):
        for content_item in output_item.get("content", []):
            text = content_item.get("text")
            if text:
                fragments.append(text)
    return "\n".join(fragment for fragment in fragments if fragment)


def _truncate_prompt(prompt: str) -> str:
    max_chars = getattr(settings, "OPENAI_DEFAULT_MAX_INSTRUCTION_CHARS", None)
    if max_chars is None or max_chars <= 0 or len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def _normalize_fingerprint(raw_value: str, fallback_seed: str) -> str:
    candidate = (raw_value or "").strip().lower()
    digest_seed = candidate or fallback_seed
    digest = hashlib.sha1(digest_seed.encode("utf-8")).hexdigest()
    return digest[:32]


def _normalize_severity(value: str) -> str:
    allowed = {choice for choice, _ in ConcernSeverity.choices}
    return value if value in allowed else ConcernSeverity.MEDIUM


def _normalize_concern_type(value: str) -> str:
    allowed = {choice for choice, _ in ConcernType.choices}
    return value if value in allowed else ConcernType.HUMAN_FLAG


def _request_openai(*, schema_name: str, schema: dict, prompt: str, max_output_tokens: int | None = None) -> tuple[str, dict]:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise ConcernError("OPENAI_API_KEY is not configured.")

    model = getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-5-mini")
    timeout_seconds = getattr(settings, "OPENAI_DEFAULT_TIMEOUT_SECONDS", None)
    if timeout_seconds is not None:
        timeout_seconds = max(timeout_seconds, 1)
    configured_max_output_tokens = (
        max_output_tokens
        if max_output_tokens is not None
        else getattr(settings, "OPENAI_DEFAULT_MAX_OUTPUT_TOKENS", None)
    )
    if configured_max_output_tokens is not None:
        configured_max_output_tokens = max(configured_max_output_tokens, 1)
    reasoning_effort = getattr(settings, "OPENAI_DEFAULT_REASONING_EFFORT", None)
    payload = {
        "model": model,
        "input": _truncate_prompt(prompt),
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if configured_max_output_tokens is not None:
        payload["max_output_tokens"] = configured_max_output_tokens
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    response = request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        if timeout_seconds is None:
            http_response_context = request.urlopen(response)
        else:
            http_response_context = request.urlopen(response, timeout=timeout_seconds)
        with http_response_context as http_response:
            body = http_response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ConcernError(f"OpenAI request failed with HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise ConcernError(f"OpenAI request failed: {exc.reason}") from exc

    response_payload = json.loads(body)
    if response_payload.get("status") == "incomplete":
        reason = (response_payload.get("incomplete_details") or {}).get("reason", "unknown")
        raise ConcernError(f"OpenAI response was incomplete (reason: {reason}).")
    output_text = _extract_output_text(response_payload).strip()
    if not output_text:
        raise ConcernError("OpenAI returned an empty concern response.")
    try:
        return model, json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ConcernError(f"OpenAI returned malformed JSON: {output_text}") from exc


def _project_concern_prompt(snapshot: dict, scopes: tuple[str, ...]) -> str:
    return (
        "You are reviewing a collaborative product spec workspace.\n"
        "Raise only important project issues that the team should discuss or fix.\n"
        "Available concern types: consistency, implementability, usability, business_viability.\n"
        f"Only use these concern types: {', '.join(scopes)}.\n"
        "Ground every concern in the provided spec sections, decisions, or assumptions.\n"
        "Do not invent product requirements outside the snapshot.\n"
        "Prefer fewer, higher-signal concerns.\n"
        f"Project snapshot JSON:\n{json.dumps(snapshot, ensure_ascii=True)}"
    )


def _targeted_reevaluation_prompt(snapshot: dict, concern: ProjectConcern) -> str:
    return (
        "You are re-evaluating whether a previously raised project concern is still valid.\n"
        "Return 'resolved' only when the current spec sections and decisions materially address the concern.\n"
        "Otherwise keep it 'open'.\n"
        f"Concern JSON:\n{json.dumps(_serialize_concern(concern), ensure_ascii=True)}\n\n"
        f"Project snapshot JSON:\n{json.dumps(snapshot, ensure_ascii=True)}"
    )


def _proposal_prompt(snapshot: dict, concern: ProjectConcern, sections: list[dict]) -> str:
    payload = [
        {
            "section_id": section["id"],
            "section_title": section["title"],
            "status": section["status"],
            "body": section["body"],
        }
        for section in sections
    ]
    return (
        "You are helping a team resolve a project concern.\n"
        "Produce reviewable per-section body rewrites. Do not rename or reorder sections.\n"
        "Only return changes for sections that should actually be edited.\n"
        "Keep the edits concrete and internally consistent.\n"
        f"Concern JSON:\n{json.dumps(_serialize_concern(concern), ensure_ascii=True)}\n\n"
        f"Relevant sections JSON:\n{json.dumps(payload, ensure_ascii=True)}\n\n"
        f"Project snapshot JSON:\n{json.dumps(snapshot, ensure_ascii=True)}"
    )


def _serialize_concern(concern: ProjectConcern) -> dict:
    refs = concern.node_refs or []
    return {
        "id": concern.id,
        "fingerprint": concern.fingerprint,
        "concern_type": concern.concern_type,
        "raised_by_kind": concern.raised_by_kind,
        "title": concern.title,
        "summary": concern.summary,
        "severity": concern.severity,
        "status": concern.status,
        "recommendation": concern.recommendation,
        "source_refs": concern.source_refs,
        "node_refs": refs,
    }


def _normalized_ref(ref: dict) -> dict:
    return {
        "section_id": ref.get("section_id", ""),
        "node_id": ref.get("node_id", ""),
        "label": ref.get("label", ""),
        "excerpt": ref.get("excerpt", ""),
    }


def _unique_refs(refs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for ref in refs:
        normalized = _normalized_ref(ref)
        section_id = normalized["section_id"]
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        unique.append(normalized)
    return unique


def _link_section_refs_from_refs(project, source_refs: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for source_ref in source_refs or []:
        kind = source_ref.get("kind", "")
        if kind not in {"document", "section"}:
            continue
        primary_ref = build_primary_ref_for_identifier(project, source_ref.get("identifier", ""))
        if not primary_ref:
            continue
        if source_ref.get("label"):
            primary_ref["label"] = source_ref["label"]
        refs.append(primary_ref)
    return _unique_refs(refs)


def _spec_section_catalog(project) -> list[dict]:
    return section_catalog(ensure_spec_document(project).content_json)


def _find_sections_for_refs(project, refs: list[dict]) -> list[dict]:
    spec_document = ensure_spec_document(project)
    sections: list[dict] = []
    seen: set[str] = set()
    for ref in refs:
        section_id = ref.get("section_id", "")
        if not section_id or section_id in seen:
            continue
        section = find_section(spec_document.content_json, section_id)
        if not section:
            continue
        seen.add(section_id)
        sections.append(section_summary(section))
    return sections


def concern_sort_key(concern: ProjectConcern):
    status_weight = {
        ConcernStatus.OPEN: 0,
        ConcernStatus.STALE: 1,
        ConcernStatus.RESOLVED: 2,
        ConcernStatus.DISMISSED: 3,
    }
    severity_weight = {
        ConcernSeverity.CRITICAL: 0,
        ConcernSeverity.HIGH: 1,
        ConcernSeverity.MEDIUM: 2,
        ConcernSeverity.LOW: 3,
    }
    return (
        status_weight.get(concern.status, 4),
        severity_weight.get(concern.severity, 4),
        -(concern.last_seen_at or concern.updated_at or concern.created_at).timestamp(),
    )


def ordered_concerns(project):
    concerns = list(project.concerns.prefetch_related("proposals__changes", "posts").all())
    return sorted(concerns, key=concern_sort_key)


def render_proposal_change_diff(change: ConcernProposalChange) -> str:
    current_body = change.original_body or blocks_to_markdown(change.original_section_json.get("content", []))
    proposed_body = change.proposed_body or blocks_to_markdown(change.proposed_section_json.get("content", []))
    section_name = change.section_title or change.section_ref.get("label") or "section"
    diff_lines = difflib.unified_diff(
        (current_body or "").splitlines(),
        (proposed_body or "").splitlines(),
        fromfile=f"{section_name}:current",
        tofile=f"{section_name}:proposal",
        lineterm="",
    )
    return "\n".join(diff_lines) or "No textual diff available."


def analyze_project_concerns(snapshot: dict, scopes: tuple[str, ...] = AI_CONCERN_SCOPES) -> ConcernAnalysisResult:
    model, parsed_output = _request_openai(
        schema_name="project_concern_analysis",
        schema=CONCERN_ANALYSIS_SCHEMA,
        prompt=_project_concern_prompt(snapshot, scopes),
    )
    concerns = parsed_output.get("concerns")
    if not isinstance(concerns, list):
        raise ConcernError("OpenAI response did not include a concerns list.")
    return ConcernAnalysisResult(provider="openai", model=model, concerns=concerns)


def reevaluate_concern_with_ai(snapshot: dict, concern: ProjectConcern) -> ConcernReevaluationResult:
    model, parsed_output = _request_openai(
        schema_name="concern_reevaluation",
        schema=CONCERN_REEVALUATION_SCHEMA,
        prompt=_targeted_reevaluation_prompt(snapshot, concern),
    )
    return ConcernReevaluationResult(
        provider="openai",
        model=model,
        status=parsed_output["status"],
        title=parsed_output["title"],
        summary=parsed_output["summary"],
        severity=_normalize_severity(parsed_output["severity"]),
        recommendation=parsed_output["recommendation"],
        source_refs=parsed_output["source_refs"],
    )


def build_concern_proposal_with_ai(snapshot: dict, concern: ProjectConcern, sections: list[dict]) -> ConcernProposalResult:
    max_output_tokens = getattr(
        settings,
        "OPENAI_CONCERN_PROPOSAL_MAX_OUTPUT_TOKENS",
        getattr(settings, "OPENAI_DEFAULT_MAX_OUTPUT_TOKENS", None),
    )
    model, parsed_output = _request_openai(
        schema_name="concern_resolution_proposal",
        schema=CONCERN_PROPOSAL_SCHEMA,
        prompt=_proposal_prompt(snapshot, concern, sections),
        max_output_tokens=max_output_tokens,
    )
    return ConcernProposalResult(
        provider="openai",
        model=model,
        summary=parsed_output["summary"],
        changes=parsed_output["changes"],
    )


def create_human_concern_from_post(post, actor=None):
    if getattr(post, "concern_id", None):
        return post.concern

    inferred_refs = collect_refs_from_text(ensure_spec_document(post.project).content_json, post.body)
    title = post.body.splitlines()[0].strip()[:120] or "Team concern"
    concern = ProjectConcern.objects.create(
        project=post.project,
        source_post=post,
        fingerprint=_normalize_fingerprint(f"stream-post-{post.id}", f"stream-post-{post.id}"),
        concern_type=ConcernType.HUMAN_FLAG,
        raised_by_kind=ConcernRaisedByKind.HUMAN if post.author_id else ConcernRaisedByKind.SYSTEM,
        title=title,
        summary=post.body,
        severity=ConcernSeverity.MEDIUM,
        status=ConcernStatus.OPEN,
        recommendation="Discuss the concern and update the linked sections before re-evaluating it.",
        source_refs=[
            {"kind": "stream_post", "identifier": str(post.id), "label": f"Activity post #{post.id}"},
            *[
                {"kind": "section", "identifier": ref["section_id"], "label": ref["label"]}
                for ref in inferred_refs
            ],
        ],
        node_refs=_unique_refs(inferred_refs),
        detected_at=post.created_at,
        last_seen_at=post.created_at,
        created_by=actor if getattr(actor, "pk", None) else post.author,
    )
    post.concern = concern
    post.save(update_fields=["concern", "updated_at"])
    log_audit_event(
        project=post.project,
        actor=actor or post.author,
        event_type=AuditEventType.CONCERN_PROMOTED,
        title=f"Promoted post #{post.id} to concern",
        description=concern.title,
        source_post=post,
        metadata={"concern_id": concern.id, "fingerprint": concern.fingerprint},
    )
    return concern


def upsert_ai_concerns(*, project, run: ConcernRun, concerns: list[dict]):
    now = timezone.now()
    seen = 0
    for concern_payload in concerns:
        title = (concern_payload.get("title") or "").strip()
        summary = (concern_payload.get("summary") or "").strip()
        fallback_seed = json.dumps(
            {
                "title": title,
                "summary": summary,
                "type": concern_payload.get("concern_type", ""),
                "source_refs": concern_payload.get("source_refs", []),
            },
            sort_keys=True,
        )
        fingerprint = _normalize_fingerprint(concern_payload.get("fingerprint", ""), fallback_seed)
        node_refs = _link_section_refs_from_refs(project, concern_payload.get("source_refs", []))
        concern, created = ProjectConcern.objects.get_or_create(
            project=project,
            fingerprint=fingerprint,
            defaults={
                "run": run,
                "concern_type": _normalize_concern_type(concern_payload.get("concern_type", "")),
                "raised_by_kind": ConcernRaisedByKind.AI,
                "title": title or "Project concern",
                "summary": summary,
                "severity": _normalize_severity(concern_payload.get("severity", "")),
                "status": ConcernStatus.OPEN,
                "recommendation": concern_payload.get("recommendation", ""),
                "source_refs": concern_payload.get("source_refs", []),
                "node_refs": node_refs,
                "detected_at": now,
                "last_seen_at": now,
                "last_reevaluated_at": now,
            },
        )
        if not created:
            concern.run = run
            concern.concern_type = _normalize_concern_type(concern_payload.get("concern_type", concern.concern_type))
            concern.raised_by_kind = ConcernRaisedByKind.AI
            concern.title = title or concern.title
            concern.summary = summary or concern.summary
            concern.severity = _normalize_severity(concern_payload.get("severity", concern.severity))
            concern.recommendation = concern_payload.get("recommendation", concern.recommendation)
            concern.source_refs = concern_payload.get("source_refs", concern.source_refs)
            concern.node_refs = node_refs
            concern.last_seen_at = now
            concern.last_reevaluated_at = now
            concern.reevaluation_requested_at = None
            if concern.status in {ConcernStatus.RESOLVED, ConcernStatus.DISMISSED, ConcernStatus.STALE}:
                concern.status = ConcernStatus.OPEN
                concern.resolved_at = None
                concern.dismissed_at = None
            concern.save()
        seen += 1
    run.concern_count = seen
    run.save(update_fields=["concern_count", "updated_at"])


def run_project_concerns(project, actor=None, scopes: tuple[str, ...] = AI_CONCERN_SCOPES, trigger: str = "manual"):
    snapshot = build_project_snapshot(project)
    run = ConcernRun.objects.create(project=project, provider="openai", model="", scopes=list(scopes), trigger=trigger)
    try:
        result = analyze_project_concerns(snapshot, scopes=scopes)
    except ConcernError as exc:
        run.status = ConcernRunStatus.FAILED
        run.error_message = str(exc)
        run.save(update_fields=["status", "error_message", "updated_at"])
        log_audit_event(
            project=project,
            actor=actor,
            event_type=AuditEventType.CONCERN_RUN_FAILED,
            title="Concern scan failed",
            description=str(exc),
            metadata={"provider": "openai", "trigger": trigger},
        )
        return run

    run.provider = result.provider
    run.model = result.model
    run.status = ConcernRunStatus.COMPLETED
    run.error_message = ""
    run.analyzed_at = timezone.now()
    run.save(update_fields=["provider", "model", "status", "error_message", "analyzed_at", "updated_at"])
    upsert_ai_concerns(project=project, run=run, concerns=result.concerns)
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.CONCERN_RUN_COMPLETED,
        title="Concern scan completed",
        description=f"Found {run.concern_count} concern(s).",
        metadata={"provider": result.provider, "model": result.model, "trigger": trigger, "concern_count": run.concern_count},
    )
    return run


def queue_concern_reevaluation(concern: ProjectConcern, *, actor=None, trigger: str = "spec_section_update"):
    if concern.status == ConcernStatus.DISMISSED:
        return None

    now = timezone.now()
    changed = False
    if concern.status != ConcernStatus.STALE:
        concern.status = ConcernStatus.STALE
        changed = True
    concern.reevaluation_requested_at = now
    concern.save(update_fields=["status", "reevaluation_requested_at", "updated_at"])
    pending_run = concern.project.concern_runs.filter(
        status=ConcernRunStatus.PENDING,
        target_concern_fingerprint=concern.fingerprint,
    ).first()
    if pending_run:
        return pending_run
    pending_run = ConcernRun.objects.create(
        project=concern.project,
        provider="openai",
        model="",
        status=ConcernRunStatus.PENDING,
        scopes=[concern.concern_type],
        trigger=trigger,
        target_concern_fingerprint=concern.fingerprint,
    )
    if changed:
        log_audit_event(
            project=concern.project,
            actor=actor,
            event_type=AuditEventType.CONCERN_MARKED_STALE,
            title=f"Concern marked stale: {concern.title}",
            description=concern.summary,
            source_post=concern.source_post,
            metadata={"concern_id": concern.id, "fingerprint": concern.fingerprint, "trigger": trigger},
        )
    return pending_run


def mark_linked_concerns_stale(*, project, section_ids: list[str], actor=None, trigger: str = "spec_section_update"):
    normalized_ids = {section_id for section_id in section_ids if section_id}
    if not normalized_ids:
        return
    concerns = project.concerns.exclude(status=ConcernStatus.DISMISSED)
    for concern in concerns:
        concern_section_ids = {ref.get("section_id", "") for ref in concern.node_refs or []}
        if concern_section_ids.intersection(normalized_ids):
            queue_concern_reevaluation(concern, actor=actor, trigger=trigger)


def re_evaluate_concern(concern: ProjectConcern, *, actor=None):
    snapshot = build_project_snapshot(concern.project)
    run = ConcernRun.objects.create(
        project=concern.project,
        provider="openai",
        model="",
        status=ConcernRunStatus.PENDING,
        scopes=[concern.concern_type],
        trigger="manual_reevaluation",
        target_concern_fingerprint=concern.fingerprint,
    )
    try:
        result = reevaluate_concern_with_ai(snapshot, concern)
    except ConcernError as exc:
        run.status = ConcernRunStatus.FAILED
        run.error_message = str(exc)
        run.save(update_fields=["status", "error_message", "updated_at"])
        log_audit_event(
            project=concern.project,
            actor=actor,
            event_type=AuditEventType.CONCERN_RUN_FAILED,
            title=f"Concern re-evaluation failed: {concern.title}",
            description=str(exc),
            source_post=concern.source_post,
            metadata={"concern_id": concern.id},
        )
        return run

    now = timezone.now()
    run.provider = result.provider
    run.model = result.model
    run.status = ConcernRunStatus.COMPLETED
    run.concern_count = 1 if result.status == ConcernStatus.OPEN else 0
    run.error_message = ""
    run.analyzed_at = now
    run.save(update_fields=["provider", "model", "status", "concern_count", "error_message", "analyzed_at", "updated_at"])

    concern.run = run
    concern.title = result.title or concern.title
    concern.summary = result.summary or concern.summary
    concern.severity = result.severity
    concern.recommendation = result.recommendation
    concern.source_refs = result.source_refs
    concern.node_refs = _link_section_refs_from_refs(concern.project, concern.source_refs)
    concern.last_seen_at = now
    concern.last_reevaluated_at = now
    concern.reevaluation_requested_at = None
    concern.resolved_at = now if result.status == ConcernStatus.RESOLVED else None
    concern.resolved_by = actor if result.status == ConcernStatus.RESOLVED else None
    concern.status = ConcernStatus.RESOLVED if result.status == ConcernStatus.RESOLVED else ConcernStatus.OPEN
    concern.save()
    log_audit_event(
        project=concern.project,
        actor=actor,
        event_type=AuditEventType.CONCERN_REEVALUATED,
        title=f"Concern re-evaluated: {concern.title}",
        description=concern.summary,
        source_post=concern.source_post,
        metadata={"concern_id": concern.id, "status": concern.status},
    )
    return run


def dismiss_concern(concern: ProjectConcern, *, actor=None):
    concern.status = ConcernStatus.DISMISSED
    concern.dismissed_at = timezone.now()
    concern.dismissed_by = actor
    concern.save(update_fields=["status", "dismissed_at", "dismissed_by", "updated_at"])
    log_audit_event(
        project=concern.project,
        actor=actor,
        event_type=AuditEventType.CONCERN_DISMISSED,
        title=f"Concern dismissed: {concern.title}",
        description=concern.summary,
        source_post=concern.source_post,
        metadata={"concern_id": concern.id},
    )
    return concern


def _sections_for_concern(concern: ProjectConcern) -> list[dict]:
    sections = _find_sections_for_refs(concern.project, concern.node_refs or [])
    if sections:
        return sections
    if concern.source_post_id:
        inferred_refs = collect_refs_from_text(ensure_spec_document(concern.project).content_json, concern.source_post.body)
        if inferred_refs:
            concern.node_refs = _unique_refs(inferred_refs)
            concern.save(update_fields=["node_refs", "updated_at"])
            return _find_sections_for_refs(concern.project, concern.node_refs)
    return _spec_section_catalog(concern.project)


def resolve_concern_with_ai(concern: ProjectConcern, *, actor=None):
    sections = _sections_for_concern(concern)
    if not sections:
        raise ConcernError("This concern is not linked to any sections yet.")

    snapshot = build_project_snapshot(concern.project)
    result = build_concern_proposal_with_ai(snapshot, concern, sections)
    proposal = ConcernProposal.objects.create(
        project=concern.project,
        concern=concern,
        provider=result.provider,
        model=result.model,
        summary=result.summary,
        requested_by=actor,
        status=ConcernProposalStatus.OPEN,
    )
    section_lookup = {section["id"]: section for section in sections}
    linked_refs: list[dict] = []
    for change_payload in result.changes:
        section = section_lookup.get(change_payload.get("section_id", ""))
        if not section:
            continue
        linked_refs.append(
            {
                "section_id": section["id"],
                "node_id": "",
                "label": section["title"],
                "excerpt": section["body"][:240],
            }
        )
        proposed_section_json = {
            "type": "specSection",
            "attrs": {
                "id": section["id"],
                "key": section["key"],
                "title": section["title"],
                "kind": section["kind"],
                "status": section["status"],
                "required": section["required"],
                "legacy_slug": section["legacy_slug"],
            },
            "content": markdown_to_blocks(change_payload.get("proposed_body", "")),
        }
        ConcernProposalChange.objects.create(
            proposal=proposal,
            section_ref={
                "section_id": section["id"],
                "node_id": "",
                "label": section["title"],
                "excerpt": section["body"][:240],
            },
            section_id=section["id"],
            section_title=section["title"],
            original_section_json=deepcopy(
                find_section(ensure_spec_document(concern.project).content_json, section["id"]) or {}
            ),
            proposed_section_json=proposed_section_json,
            summary=(change_payload.get("summary") or "").strip(),
            original_body=section["body"],
            proposed_body=change_payload.get("proposed_body", ""),
        )
    if linked_refs and not concern.node_refs:
        concern.node_refs = _unique_refs(linked_refs)
        concern.save(update_fields=["node_refs", "updated_at"])
    log_audit_event(
        project=concern.project,
        actor=actor,
        event_type=AuditEventType.CONCERN_PROPOSAL_CREATED,
        title=f"AI proposal generated for {concern.title}",
        description=proposal.summary,
        source_post=concern.source_post,
        metadata={"concern_id": concern.id, "proposal_id": proposal.id},
    )
    return proposal


def _refresh_proposal_status(proposal: ConcernProposal):
    statuses = list(proposal.changes.values_list("status", flat=True))
    if statuses and all(status == ConcernProposalChangeStatus.REJECTED for status in statuses):
        proposal.status = ConcernProposalStatus.REJECTED
    elif statuses and all(status == ConcernProposalChangeStatus.ACCEPTED for status in statuses):
        proposal.status = ConcernProposalStatus.COMPLETED
    elif ConcernProposalChangeStatus.ACCEPTED in statuses:
        proposal.status = ConcernProposalStatus.PARTIALLY_APPLIED
    else:
        proposal.status = ConcernProposalStatus.OPEN
    proposal.save(update_fields=["status", "updated_at"])


def accept_concern_proposal_change(change: ConcernProposalChange, *, actor=None):
    if change.status == ConcernProposalChangeStatus.ACCEPTED:
        return change
    section_id = change.section_id or change.section_ref.get("section_id", "")
    if not section_id:
        raise ConcernError("This proposal change is not linked to a section.")
    section_payload = change.proposed_section_json or {}
    update_spec_section(
        project=change.proposal.project,
        section_id=section_id,
        actor=actor,
        title=section_payload.get("attrs", {}).get("title"),
        status=section_payload.get("attrs", {}).get("status"),
        content_json=section_payload.get("content", []),
    )
    change.status = ConcernProposalChangeStatus.ACCEPTED
    change.decided_by = actor
    change.decided_at = timezone.now()
    change.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    _refresh_proposal_status(change.proposal)
    log_audit_event(
        project=change.proposal.project,
        actor=actor,
        event_type=AuditEventType.CONCERN_PROPOSAL_CHANGE_ACCEPTED,
        title=f"Accepted AI change for {change.section_title or 'section'}",
        description=change.summary,
        metadata={
            "proposal_id": change.proposal_id,
            "concern_id": change.proposal.concern_id,
            "section_id": section_id,
        },
    )
    return change


def reject_concern_proposal_change(change: ConcernProposalChange, *, actor=None):
    if change.status == ConcernProposalChangeStatus.REJECTED:
        return change
    change.status = ConcernProposalChangeStatus.REJECTED
    change.decided_by = actor
    change.decided_at = timezone.now()
    change.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    _refresh_proposal_status(change.proposal)
    log_audit_event(
        project=change.proposal.project,
        actor=actor,
        event_type=AuditEventType.CONCERN_PROPOSAL_CHANGE_REJECTED,
        title=f"Rejected AI change for {change.section_title or 'section'}",
        description=change.summary,
        metadata={
            "proposal_id": change.proposal_id,
            "concern_id": change.proposal.concern_id,
            "section_id": change.section_id,
        },
    )
    return change
