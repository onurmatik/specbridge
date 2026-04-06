from __future__ import annotations

import copy
import re
import uuid
from typing import Any

from django.utils.text import slugify

from specs.models import DocumentStatus, DocumentType

SPEC_SCHEMA_VERSION = 1

DEFAULT_SECTION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "overview",
        "title": "Overview",
        "kind": DocumentType.OVERVIEW,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
    {
        "key": "goals",
        "title": "Goals",
        "kind": DocumentType.GOALS,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
    {
        "key": "requirements",
        "title": "Requirements",
        "kind": DocumentType.REQUIREMENTS,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
    {
        "key": "ui-ux",
        "title": "UI/UX",
        "kind": DocumentType.UI_UX,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
    {
        "key": "tech-stack",
        "title": "Tech Stack",
        "kind": DocumentType.TECH_STACK,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
    {
        "key": "infra",
        "title": "Infra",
        "kind": DocumentType.INFRA,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
    {
        "key": "risks-open-questions",
        "title": "Risks & Open Questions",
        "kind": DocumentType.RISKS_OPEN_QUESTIONS,
        "status": DocumentStatus.ITERATING,
        "required": False,
    },
)

SECTION_TEXT_LIMIT = 240


def text_node(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def paragraph_node(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [text_node(text)]} if text else {"type": "paragraph", "content": []}


def bullet_list_node(items: list[str]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [paragraph_node(item.strip())],
            }
            for item in items
            if item.strip()
        ],
    }


def plain_text_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type in {"paragraph", "listItem"}:
        return "".join(plain_text_from_node(item) for item in node.get("content", []))
    if node_type == "bulletList":
        lines = []
        for item in node.get("content", []):
            value = plain_text_from_node(item).strip()
            if value:
                lines.append(f"- {value}")
        return "\n".join(lines)
    return "".join(plain_text_from_node(item) for item in node.get("content", []))


def section_plain_text(section: dict[str, Any]) -> str:
    blocks = section.get("content", []) if isinstance(section, dict) else []
    parts = [plain_text_from_node(block).strip() for block in blocks]
    return "\n\n".join(part for part in parts if part)


def markdown_to_blocks(text: str) -> list[dict[str, Any]]:
    value = (text or "").strip()
    if not value:
        return [paragraph_node("")]

    blocks: list[dict[str, Any]] = []
    for chunk in re.split(r"\n\s*\n", value):
        lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if all(line.lstrip().startswith(("-", "*")) for line in lines):
            items = [line.lstrip()[2:].strip() for line in lines if len(line.lstrip()) >= 2]
            blocks.append(bullet_list_node(items))
            continue
        paragraph_text = " ".join(line.strip() for line in lines)
        blocks.append(paragraph_node(paragraph_text))

    return blocks or [paragraph_node("")]


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    parts = [plain_text_from_node(block).strip() for block in blocks or []]
    return "\n\n".join(part for part in parts if part).strip()


def section_identifier(project, key: str) -> str:
    project_slug = getattr(project, "slug", "project")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"specbridge:{project_slug}:{key}"))


def build_section_node(
    project,
    *,
    key: str,
    title: str,
    kind: str,
    status: str = DocumentStatus.ITERATING,
    required: bool = False,
    legacy_slug: str | None = None,
    body: str = "",
) -> dict[str, Any]:
    normalized_key = slugify(key) or key or "section"
    return {
        "type": "specSection",
        "attrs": {
            "id": section_identifier(project, normalized_key),
            "key": normalized_key,
            "title": title,
            "kind": kind,
            "status": status,
            "required": bool(required),
            "legacy_slug": legacy_slug or normalized_key,
        },
        "content": markdown_to_blocks(body),
    }


def default_spec_content(project) -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            build_section_node(
                project,
                key=section["key"],
                title=section["title"],
                kind=section["kind"],
                status=section.get("status", DocumentStatus.ITERATING),
                required=section.get("required", False),
                legacy_slug=section["key"],
                body="",
            )
            for section in DEFAULT_SECTION_SPECS
        ],
    }


def normalized_spec_content(content_json: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(content_json, dict):
        return {"type": "doc", "content": []}
    content = content_json.get("content")
    if not isinstance(content, list):
        content = []
    return {"type": "doc", "content": content}


def section_nodes(content_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    return normalized_spec_content(content_json).get("content", [])


def section_attrs(section: dict[str, Any]) -> dict[str, Any]:
    return section.get("attrs", {}) if isinstance(section, dict) else {}


def section_summary(section: dict[str, Any]) -> dict[str, Any]:
    attrs = section_attrs(section)
    return {
        "id": attrs.get("id", ""),
        "key": attrs.get("key", ""),
        "title": attrs.get("title", "Untitled Section"),
        "kind": attrs.get("kind", DocumentType.CUSTOM),
        "status": attrs.get("status", DocumentStatus.ITERATING),
        "required": bool(attrs.get("required", False)),
        "legacy_slug": attrs.get("legacy_slug", attrs.get("key", "")),
        "body": blocks_to_markdown(section.get("content", [])),
        "blocks": copy.deepcopy(section.get("content", [])),
    }


def section_catalog(content_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [section_summary(section) for section in section_nodes(content_json)]


def find_section(content_json: dict[str, Any] | None, section_id: str) -> dict[str, Any] | None:
    for section in section_nodes(content_json):
        attrs = section_attrs(section)
        if attrs.get("id") == section_id:
            return section
    return None


def find_section_by_identifier(content_json: dict[str, Any] | None, identifier: str) -> dict[str, Any] | None:
    normalized = (identifier or "").strip().lower()
    if not normalized:
        return None
    for section in section_nodes(content_json):
        attrs = section_attrs(section)
        candidates = {
            str(attrs.get("id", "")).lower(),
            str(attrs.get("key", "")).lower(),
            str(attrs.get("legacy_slug", "")).lower(),
            str(attrs.get("title", "")).lower(),
        }
        if normalized in candidates:
            return section
    return None


def section_index(content_json: dict[str, Any] | None, section_id: str) -> int:
    for index, section in enumerate(section_nodes(content_json)):
        if section_attrs(section).get("id") == section_id:
            return index
    return -1


def unique_section_key(content_json: dict[str, Any] | None, desired_key: str) -> str:
    base_key = slugify(desired_key) or "section"
    existing_keys = {
        str(section_attrs(section).get("key", "")).strip()
        for section in section_nodes(content_json)
    }
    if base_key not in existing_keys:
        return base_key

    suffix = 2
    while f"{base_key}-{suffix}" in existing_keys:
        suffix += 1
    return f"{base_key}-{suffix}"


def update_section_content(
    content_json: dict[str, Any] | None,
    section_id: str,
    *,
    title: str | None = None,
    status: str | None = None,
    content_blocks: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    next_content = normalized_spec_content(copy.deepcopy(content_json))
    changed = False
    updated_section = None
    for section in next_content.get("content", []):
        attrs = section.setdefault("attrs", {})
        if attrs.get("id") != section_id:
            continue
        updated_section = section
        if title is not None and title != attrs.get("title"):
            attrs["title"] = title
            changed = True
        if status is not None and status != attrs.get("status"):
            attrs["status"] = status
            changed = True
        if content_blocks is not None and content_blocks != section.get("content", []):
            section["content"] = content_blocks
            changed = True
        break
    return next_content, updated_section, changed


def insert_section_after(
    content_json: dict[str, Any] | None,
    *,
    project,
    after_section_id: str,
    title: str = "New Section",
    kind: str = DocumentType.CUSTOM,
    status: str = DocumentStatus.ITERATING,
    required: bool = False,
    body: str = "",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    next_content = normalized_spec_content(copy.deepcopy(content_json))
    insert_after_index = section_index(next_content, after_section_id)
    if insert_after_index < 0:
        return next_content, None

    normalized_title = (title or "").strip() or "New Section"
    unique_key = unique_section_key(next_content, normalized_title)
    inserted_section = build_section_node(
        project,
        key=unique_key,
        title=normalized_title,
        kind=kind,
        status=status,
        required=required,
        legacy_slug=unique_key,
        body=body,
    )
    next_content.setdefault("content", []).insert(insert_after_index + 1, inserted_section)
    return next_content, inserted_section


def move_section(
    content_json: dict[str, Any] | None,
    section_id: str,
    *,
    direction: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    next_content = normalized_spec_content(copy.deepcopy(content_json))
    sections = next_content.setdefault("content", [])
    current_index = section_index(next_content, section_id)
    if current_index < 0:
        return next_content, None, False

    moved_section = sections[current_index]
    offset = -1 if direction == "up" else 1 if direction == "down" else 0
    target_index = current_index + offset
    if offset == 0 or target_index < 0 or target_index >= len(sections):
        return next_content, moved_section, False

    sections[current_index], sections[target_index] = sections[target_index], sections[current_index]
    return next_content, sections[target_index], True


def delete_section(
    content_json: dict[str, Any] | None,
    section_id: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool, str]:
    next_content = normalized_spec_content(copy.deepcopy(content_json))
    sections = next_content.setdefault("content", [])
    current_index = section_index(next_content, section_id)
    if current_index < 0:
        return next_content, None, False, ""

    removed_section = sections.pop(current_index)
    if not sections:
        return next_content, removed_section, True, ""

    focus_index = min(current_index, len(sections) - 1)
    focus_section_id = str(section_attrs(sections[focus_index]).get("id", ""))
    return next_content, removed_section, True, focus_section_id


def build_primary_ref(section: dict[str, Any], *, excerpt: str = "", node_id: str = "") -> dict[str, Any]:
    attrs = section_attrs(section)
    resolved_excerpt = excerpt.strip() or section_plain_text(section)[:SECTION_TEXT_LIMIT]
    return {
        "section_id": attrs.get("id", ""),
        "node_id": node_id or "",
        "label": attrs.get("title", "Untitled Section"),
        "excerpt": resolved_excerpt,
    }


def find_primary_ref_for_identifier(content_json: dict[str, Any] | None, identifier: str, *, excerpt: str = "") -> dict[str, Any]:
    section = find_section_by_identifier(content_json, identifier)
    if not section:
        return {}
    return build_primary_ref(section, excerpt=excerpt)


def collect_refs_from_text(content_json: dict[str, Any] | None, text: str) -> list[dict[str, Any]]:
    lowered = (text or "").lower()
    refs: list[dict[str, Any]] = []
    for section in section_nodes(content_json):
        attrs = section_attrs(section)
        title = str(attrs.get("title", "")).lower()
        key = str(attrs.get("key", "")).lower()
        legacy_slug = str(attrs.get("legacy_slug", "")).lower()
        if any(token and token in lowered for token in {title, key, legacy_slug}):
            refs.append(build_primary_ref(section))
    return refs


def section_title_from_ref(content_json: dict[str, Any] | None, primary_ref: dict[str, Any] | None) -> str:
    if not isinstance(primary_ref, dict):
        return ""
    section = find_section(content_json, primary_ref.get("section_id", ""))
    if not section:
        return primary_ref.get("label", "")
    return section_attrs(section).get("title", "")


def section_markdown_from_ref(content_json: dict[str, Any] | None, primary_ref: dict[str, Any] | None) -> str:
    if not isinstance(primary_ref, dict):
        return ""
    section = find_section(content_json, primary_ref.get("section_id", ""))
    if not section:
        return ""
    return blocks_to_markdown(section.get("content", []))


def section_status_from_ref(content_json: dict[str, Any] | None, primary_ref: dict[str, Any] | None) -> str:
    if not isinstance(primary_ref, dict):
        return DocumentStatus.ITERATING
    section = find_section(content_json, primary_ref.get("section_id", ""))
    if not section:
        return DocumentStatus.ITERATING
    return section_attrs(section).get("status", DocumentStatus.ITERATING)
