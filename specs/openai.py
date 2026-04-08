from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings

from specs.models import AIUsageRecord

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass
class OpenAIUsageContext:
    project: object
    operation: str
    actor: object | None = None
    concern: object | None = None
    concern_run: object | None = None
    consistency_run: object | None = None
    context_metadata: dict | None = None


@dataclass
class OpenAIResponsePayload:
    provider: str
    model: str
    response_id: str
    response_status: str
    output_text: str
    response_payload: dict
    usage_record: AIUsageRecord | None = None


def extract_output_text(response_payload: dict) -> str:
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


def truncate_prompt(prompt: str) -> str:
    max_chars = getattr(settings, "OPENAI_DEFAULT_MAX_INSTRUCTION_CHARS", None)
    if max_chars is None or max_chars <= 0 or len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def _coerce_int(value) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _usage_dict(response_payload: dict) -> dict:
    usage = response_payload.get("usage")
    return usage if isinstance(usage, dict) else {}


def record_ai_usage(*, usage_context: OpenAIUsageContext | None, provider: str, model: str, response_payload: dict):
    if usage_context is None or getattr(usage_context.project, "pk", None) is None:
        return None

    usage = _usage_dict(response_payload)
    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")
    input_details = input_details if isinstance(input_details, dict) else {}
    output_details = output_details if isinstance(output_details, dict) else {}

    return AIUsageRecord.objects.create(
        project=usage_context.project,
        organization=usage_context.project.organization,
        user=usage_context.actor if getattr(usage_context.actor, "pk", None) else None,
        concern=usage_context.concern,
        concern_run=usage_context.concern_run,
        consistency_run=usage_context.consistency_run,
        provider=provider,
        model=model,
        operation=usage_context.operation,
        response_id=str(response_payload.get("id") or ""),
        response_status=str(response_payload.get("status") or ""),
        input_tokens=_coerce_int(usage.get("input_tokens")),
        output_tokens=_coerce_int(usage.get("output_tokens")),
        reasoning_tokens=_coerce_int(
            output_details.get("reasoning_tokens") or usage.get("reasoning_tokens")
        ),
        cached_input_tokens=_coerce_int(
            input_details.get("cached_tokens") or usage.get("cached_input_tokens")
        ),
        total_tokens=_coerce_int(usage.get("total_tokens")),
        usage_details=copy.deepcopy(usage),
        context_metadata=copy.deepcopy(usage_context.context_metadata or {}),
    )


def request_openai_json_schema(
    *,
    schema_name: str,
    schema: dict,
    prompt: str,
    error_cls,
    empty_output_message: str,
    incomplete_output_message: str | None = None,
    max_output_tokens: int | None = None,
    usage_context: OpenAIUsageContext | None = None,
) -> OpenAIResponsePayload:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise error_cls("OPENAI_API_KEY is not configured.")

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
        "input": truncate_prompt(prompt),
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
        raise error_cls(f"OpenAI request failed with HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise error_cls(f"OpenAI request failed: {exc.reason}") from exc

    response_payload = json.loads(body)
    effective_model = response_payload.get("model") or model
    usage_record = record_ai_usage(
        usage_context=usage_context,
        provider="openai",
        model=effective_model,
        response_payload=response_payload,
    )
    if incomplete_output_message and response_payload.get("status") == "incomplete":
        reason = (response_payload.get("incomplete_details") or {}).get("reason", "unknown")
        raise error_cls(incomplete_output_message.format(reason=reason))

    output_text = extract_output_text(response_payload).strip()
    if not output_text:
        raise error_cls(empty_output_message)
    return OpenAIResponsePayload(
        provider="openai",
        model=effective_model,
        response_id=str(response_payload.get("id") or ""),
        response_status=str(response_payload.get("status") or ""),
        output_text=output_text,
        response_payload=response_payload,
        usage_record=usage_record,
    )
