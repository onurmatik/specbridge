from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from specs.models import (
    AuditEventType,
    ConsistencyIssue,
    ConsistencyIssueSeverity,
    ConsistencyIssueStatus,
    ConsistencyRun,
    ConsistencyRunStatus,
)
from specs.services import build_project_snapshot, log_audit_event

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

CONSISTENCY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fingerprint": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
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
    "required": ["issues"],
}


class ConsistencyError(Exception):
    pass


@dataclass
class ConsistencyAnalysisResult:
    provider: str
    model: str
    issues: list[dict]


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


def _normalize_fingerprint(raw_value: str, fallback_seed: str) -> str:
    candidate = (raw_value or "").strip().lower()
    if candidate:
        digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()
    else:
        digest = hashlib.sha1(fallback_seed.encode("utf-8")).hexdigest()
    return digest[:32]


def _normalize_severity(value: str) -> str:
    allowed = {
        ConsistencyIssueSeverity.LOW,
        ConsistencyIssueSeverity.MEDIUM,
        ConsistencyIssueSeverity.HIGH,
        ConsistencyIssueSeverity.CRITICAL,
    }
    return value if value in allowed else ConsistencyIssueSeverity.MEDIUM


def _analysis_prompt(snapshot: dict) -> str:
    return (
        "You are a consistency checker for a multi-document product planning workspace.\n"
        "Review the project snapshot and identify contradictions, missing links, or decisions "
        "that conflict with documents or assumptions.\n"
        "Only report issues that are materially actionable and grounded in the provided data.\n"
        "Focus on:\n"
        "1. Document-vs-document contradictions.\n"
        "2. Decision-vs-document contradictions.\n"
        "3. Assumption-vs-document or assumption-vs-decision contradictions.\n"
        "4. Important missing references when a decision or assumption is clearly not reflected in a document.\n"
        "Do not invent product requirements outside the provided snapshot.\n"
        f"Project snapshot JSON:\n{json.dumps(snapshot, ensure_ascii=True)}"
    )


def _truncate_prompt(prompt: str) -> str:
    max_chars = max(getattr(settings, "OPENAI_DEFAULT_MAX_INSTRUCTION_CHARS", 20000), 0)
    if not max_chars or len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def analyze_project_consistency(snapshot: dict) -> ConsistencyAnalysisResult:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise ConsistencyError("OPENAI_API_KEY is not configured.")

    model = getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-5-mini")
    timeout_seconds = max(getattr(settings, "OPENAI_DEFAULT_TIMEOUT_SECONDS", 60), 1)
    max_output_tokens = max(getattr(settings, "OPENAI_DEFAULT_MAX_OUTPUT_TOKENS", 1200), 1)
    reasoning_effort = getattr(settings, "OPENAI_DEFAULT_REASONING_EFFORT", "low")
    payload = {
        "model": model,
        "input": _truncate_prompt(_analysis_prompt(snapshot)),
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "consistency_analysis",
                "strict": True,
                "schema": CONSISTENCY_SCHEMA,
            }
        },
    }
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
        with request.urlopen(response, timeout=timeout_seconds) as http_response:
            body = http_response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ConsistencyError(f"OpenAI request failed with HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise ConsistencyError(f"OpenAI request failed: {exc.reason}") from exc

    response_payload = json.loads(body)
    output_text = _extract_output_text(response_payload).strip()
    if not output_text:
        raise ConsistencyError("OpenAI returned an empty consistency analysis.")

    try:
        parsed_output = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ConsistencyError(f"OpenAI returned malformed JSON: {output_text}") from exc

    issues = parsed_output.get("issues")
    if not isinstance(issues, list):
        raise ConsistencyError("OpenAI response did not include an issues list.")
    return ConsistencyAnalysisResult(provider="openai", model=model, issues=issues)


def upsert_consistency_issues(*, project, run: ConsistencyRun, issues: list[dict]):
    now = timezone.now()
    seen = 0
    for issue_payload in issues:
        title = (issue_payload.get("title") or "").strip()
        summary = (issue_payload.get("summary") or "").strip()
        fallback_seed = json.dumps(
            {
                "title": title,
                "summary": summary,
                "source_refs": issue_payload.get("source_refs", []),
            },
            sort_keys=True,
        )
        fingerprint = _normalize_fingerprint(issue_payload.get("fingerprint", ""), fallback_seed)
        issue, created = ConsistencyIssue.objects.get_or_create(
            project=project,
            fingerprint=fingerprint,
            defaults={
                "run": run,
                "title": title or "Consistency issue",
                "summary": summary,
                "severity": _normalize_severity(issue_payload.get("severity", "")),
                "source_refs": issue_payload.get("source_refs", []),
                "recommendation": issue_payload.get("recommendation", ""),
                "detected_at": now,
                "last_seen_at": now,
                "status": ConsistencyIssueStatus.OPEN,
            },
        )
        if created:
            seen += 1
            continue

        issue.run = run
        issue.title = title or issue.title
        issue.summary = summary or issue.summary
        issue.severity = _normalize_severity(issue_payload.get("severity", issue.severity))
        issue.source_refs = issue_payload.get("source_refs", issue.source_refs)
        issue.recommendation = issue_payload.get("recommendation", issue.recommendation)
        issue.last_seen_at = now
        if issue.status in {ConsistencyIssueStatus.RESOLVED, ConsistencyIssueStatus.DISMISSED}:
            issue.status = ConsistencyIssueStatus.OPEN
            issue.resolved_at = None
            issue.dismissed_at = None
        issue.save()
        seen += 1
    run.issue_count = seen
    run.save(update_fields=["issue_count", "updated_at"])


def run_project_consistency(project) -> ConsistencyRun:
    snapshot = build_project_snapshot(project)
    run = ConsistencyRun.objects.create(project=project, provider="openai", model="")
    try:
        result = analyze_project_consistency(snapshot)
    except ConsistencyError as exc:
        run.status = ConsistencyRunStatus.FAILED
        run.error_message = str(exc)
        run.save(update_fields=["status", "error_message", "updated_at"])
        log_audit_event(
            project=project,
            event_type=AuditEventType.CONSISTENCY_RUN_FAILED,
            title="Consistency check failed",
            description=str(exc),
            metadata={"provider": "openai"},
        )
        return run

    run.provider = result.provider
    run.model = result.model
    run.status = ConsistencyRunStatus.COMPLETED
    run.error_message = ""
    run.analyzed_at = timezone.now()
    run.save(update_fields=["provider", "model", "status", "error_message", "analyzed_at", "updated_at"])
    upsert_consistency_issues(project=project, run=run, issues=result.issues)
    log_audit_event(
        project=project,
        event_type=AuditEventType.CONSISTENCY_RUN_COMPLETED,
        title="Consistency check completed",
        description=f"Found {run.issue_count} issue(s).",
        metadata={"provider": result.provider, "model": result.model, "issue_count": run.issue_count},
    )
    return run


def resolve_consistency_issue(*, issue: ConsistencyIssue, actor=None):
    issue.status = ConsistencyIssueStatus.RESOLVED
    issue.resolved_at = timezone.now()
    issue.save(update_fields=["status", "resolved_at", "updated_at"])
    log_audit_event(
        project=issue.project,
        actor=actor,
        event_type=AuditEventType.CONSISTENCY_ISSUE_RESOLVED,
        title=f"Resolved consistency issue: {issue.title}",
        description=issue.summary,
        metadata={"issue_id": issue.id, "fingerprint": issue.fingerprint},
    )
    return issue


def dismiss_consistency_issue(*, issue: ConsistencyIssue, actor=None):
    issue.status = ConsistencyIssueStatus.DISMISSED
    issue.dismissed_at = timezone.now()
    issue.save(update_fields=["status", "dismissed_at", "updated_at"])
    log_audit_event(
        project=issue.project,
        actor=actor,
        event_type=AuditEventType.CONSISTENCY_ISSUE_DISMISSED,
        title=f"Dismissed consistency issue: {issue.title}",
        description=issue.summary,
        metadata={"issue_id": issue.id, "fingerprint": issue.fingerprint},
    )
    return issue
