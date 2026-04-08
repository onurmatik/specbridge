from __future__ import annotations

import json
from dataclasses import dataclass

from specs.models import AIUsageOperation
from specs.openai import OpenAIUsageContext, request_openai_json_schema
from specs.services import ensure_spec_document
from specs.spec_document import find_section, section_summary, strip_redundant_section_heading

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


def _request_openai(
    *,
    schema_name: str,
    schema: dict,
    prompt: str,
    usage_context: OpenAIUsageContext | None = None,
) -> tuple[str, dict]:
    response = request_openai_json_schema(
        schema_name=schema_name,
        schema=schema,
        prompt=prompt,
        error_cls=SectionRevisionError,
        empty_output_message="OpenAI returned an empty section revision.",
        usage_context=usage_context,
    )
    try:
        return response.model, json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise SectionRevisionError(f"OpenAI returned malformed JSON: {response.output_text}") from exc


def _section_revision_prompt(*, prompt: str, title: str, kind: str, status: str, body: str) -> str:
    return (
        "You are revising a single section from a collaborative product specification.\n"
        "Operate only on the supplied section body.\n"
        "Do not change the section title, section status, or document type.\n"
        "Do not repeat the section title as a heading or opening line in the revised body.\n"
        "Always return the revised section and summary in English, even if the user's request or the current "
        "section body is written in another language.\n"
        "Do not add new requirements, owners, metrics, integrations, dates, APIs, decisions, or implementation "
        "details that are not already supported by the current text.\n"
        "Do not reference other sections unless the current body already does.\n"
        "Treat the user's request as an editing instruction, not as permission to expand product scope.\n"
        "Return markdown-friendly body text using paragraphs, subheadings, bullet lists, and numbered lists when helpful.\n"
        "Nested lists are allowed when they improve clarity.\n"
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
    actor=None,
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
        usage_context=OpenAIUsageContext(
            project=project,
            actor=actor,
            operation=AIUsageOperation.SECTION_REVISION,
            context_metadata={
                "section_id": section_data["id"],
                "section_key": section_data["key"],
                "section_title": effective_title,
                "action": action or "",
            },
        ),
    )
    revised_body = strip_redundant_section_heading(parsed_output.get("revised_body") or "", effective_title)
    if not revised_body:
        raise SectionRevisionError("OpenAI did not return revised section content.")

    return SectionRevisionResult(
        provider="openai",
        model=model,
        prompt=resolved_prompt,
        summary=(parsed_output.get("summary") or "Section revised").strip(),
        revised_body=revised_body,
    )
