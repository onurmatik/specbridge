from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings

from specs.services import ensure_spec_document
from specs.spec_document import find_section, section_summary

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

SECTION_REVISION_ACTIONS = {
    "revise": {
        "label": "Revise",
        "instruction": (
            "Revise the section so it reads cleaner and more professionally while preserving the original intent, "
            "scope, and commitments."
        ),
    },
    "grammar": {
        "label": "Fix grammar",
        "instruction": (
            "Correct grammar, spelling, punctuation, and awkward phrasing. Preserve the original meaning, "
            "structure, and level of detail."
        ),
    },
    "clarify": {
        "label": "Clarify",
        "instruction": (
            "Rewrite for clarity and readability. Keep the same scope and commitments, but make the wording "
            "cleaner and easier to scan."
        ),
    },
    "summarize": {
        "label": "Summarize",
        "instruction": (
            "Condense the section into a shorter version. Preserve all important commitments and constraints, "
            "but remove repetition and low-signal filler."
        ),
    },
    "detail": {
        "label": "Add detail",
        "instruction": (
            "Add useful detail and connective explanation, but only by unpacking what is already present in the "
            "text. Do not invent new requirements, metrics, owners, integrations, dates, or technical choices."
        ),
    },
}

SECTION_REVISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "revised_body": {"type": "string"},
    },
    "required": ["summary", "revised_body"],
}


class SectionRevisionError(Exception):
    pass


@dataclass
class SectionRevisionResult:
    provider: str
    model: str
    prompt: str
    summary: str
    revised_body: str


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
    max_chars = max(getattr(settings, "OPENAI_DEFAULT_MAX_INSTRUCTION_CHARS", 20000), 0)
    if not max_chars or len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def _request_openai(*, schema_name: str, schema: dict, prompt: str) -> tuple[str, dict]:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise SectionRevisionError("OPENAI_API_KEY is not configured.")

    model = getattr(settings, "OPENAI_DEFAULT_MODEL", "gpt-5-mini")
    timeout_seconds = max(getattr(settings, "OPENAI_DEFAULT_TIMEOUT_SECONDS", 60), 1)
    max_output_tokens = max(getattr(settings, "OPENAI_DEFAULT_MAX_OUTPUT_TOKENS", 1200), 1)
    reasoning_effort = getattr(settings, "OPENAI_DEFAULT_REASONING_EFFORT", "low")
    payload = {
        "model": model,
        "input": _truncate_prompt(prompt),
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
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
        raise SectionRevisionError(f"OpenAI request failed with HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise SectionRevisionError(f"OpenAI request failed: {exc.reason}") from exc

    response_payload = json.loads(body)
    output_text = _extract_output_text(response_payload).strip()
    if not output_text:
        raise SectionRevisionError("OpenAI returned an empty section revision.")
    try:
        return model, json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise SectionRevisionError(f"OpenAI returned malformed JSON: {output_text}") from exc


def _section_revision_prompt(*, prompt: str, title: str, kind: str, status: str, body: str) -> str:
    return (
        "You are revising a single section from a collaborative product specification.\n"
        "Operate only on the supplied section body.\n"
        "Do not change the section title, section status, or document type.\n"
        "Do not add new requirements, owners, metrics, integrations, dates, APIs, decisions, or implementation "
        "details that are not already supported by the current text.\n"
        "Do not reference other sections unless the current body already does.\n"
        "Treat the user's request as an editing instruction, not as permission to expand product scope.\n"
        "Return markdown-friendly body text using paragraphs and bullet lists only when helpful.\n"
        f"User revision request: {prompt}\n\n"
        f"Section title: {title}\n"
        f"Section kind: {kind}\n"
        f"Section status: {status}\n\n"
        "Current body:\n"
        f"{body}"
    )


def revise_section_with_ai(
    *,
    project,
    section_id: str,
    prompt: str | None = None,
    action: str | None = None,
    title: str | None = None,
    body: str | None = None,
) -> SectionRevisionResult:
    section = find_section(ensure_spec_document(project).content_json, section_id)
    if not section:
        raise SectionRevisionError("Section not found.")

    resolved_prompt = (prompt or "").strip()
    if not resolved_prompt and action:
        action_config = SECTION_REVISION_ACTIONS.get(action)
        if action_config:
            resolved_prompt = action_config["instruction"]

    if not resolved_prompt:
        raise SectionRevisionError("Enter a revision prompt before running AI.")

    if action and action not in SECTION_REVISION_ACTIONS:
        raise SectionRevisionError("Unsupported section revision action.")

    section_data = section_summary(section)
    effective_title = (title if title is not None else section_data["title"]).strip() or section_data["title"]
    effective_body = body if body is not None else section_data["body"]
    if not effective_body.strip():
        raise SectionRevisionError("Write section content before requesting an AI revision.")

    model, parsed_output = _request_openai(
        schema_name="section_revision",
        schema=SECTION_REVISION_SCHEMA,
        prompt=_section_revision_prompt(
            prompt=resolved_prompt,
            title=effective_title,
            kind=section_data["kind"],
            status=section_data["status"],
            body=effective_body,
        ),
    )
    revised_body = (parsed_output.get("revised_body") or "").strip()
    if not revised_body:
        raise SectionRevisionError("OpenAI did not return revised section content.")

    return SectionRevisionResult(
        provider="openai",
        model=model,
        prompt=resolved_prompt,
        summary=(parsed_output.get("summary") or "Section revised").strip(),
        revised_body=revised_body,
    )
