from __future__ import annotations

import copy
import re
import uuid
from typing import Any

from django.utils.text import slugify

from specs.models import DocumentStatus, DocumentType

SPEC_SCHEMA_VERSION = 2
HEADING_PATTERN = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
LIST_ITEM_PATTERN = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
INLINE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("***", ("bold", "italic")),
    ("___", ("bold", "italic")),
    ("**", ("bold",)),
    ("__", ("bold",)),
    ("*", ("italic",)),
    ("_", ("italic",)),
)
SUPPORTED_INLINE_MARKS = ("bold", "italic")

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


def _normalized_mark_types(marks: list[dict[str, Any]] | list[str] | tuple[str, ...] | None) -> list[str]:
    normalized: list[str] = []
    for mark in marks or []:
        mark_type = mark.get("type") if isinstance(mark, dict) else str(mark or "")
        if mark_type in SUPPORTED_INLINE_MARKS and mark_type not in normalized:
            normalized.append(mark_type)
    return [mark_type for mark_type in SUPPORTED_INLINE_MARKS if mark_type in normalized]


def _mark_objects(mark_types: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    return [{"type": mark_type} for mark_type in _normalized_mark_types(mark_types)]


def _merged_mark_types(
    existing: list[str] | tuple[str, ...] | None,
    extra: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    merged = _normalized_mark_types([*list(existing or ()), *list(extra or ())])
    return tuple(merged)


def text_node(text: str, marks: list[dict[str, Any]] | list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    node = {"type": "text", "text": text}
    normalized_marks = _mark_objects(marks)
    if normalized_marks:
        node["marks"] = normalized_marks
    return node


def _mark_signature(node: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_normalized_mark_types(node.get("marks")))


def _append_inline_text(
    nodes: list[dict[str, Any]],
    text: str,
    marks: list[str] | tuple[str, ...] | None = None,
) -> None:
    if not text:
        return
    normalized_marks = _mark_objects(marks)
    if nodes and nodes[-1].get("type") == "text" and _mark_signature(nodes[-1]) == tuple(
        _normalized_mark_types(marks)
    ):
        nodes[-1]["text"] = f"{nodes[-1].get('text', '')}{text}"
        return
    nodes.append(text_node(text, normalized_marks))


def _underscore_token_is_word_internal(text: str, token_index: int, token: str) -> bool:
    if not token.startswith("_"):
        return False
    before = text[token_index - 1] if token_index > 0 else ""
    after_index = token_index + len(token)
    after = text[after_index] if after_index < len(text) else ""
    return before.isalnum() and after.isalnum()


def _find_closing_inline_token(text: str, token: str, start_index: int) -> int:
    index = start_index
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text.startswith(token, index):
            if token.startswith("_") and _underscore_token_is_word_internal(text, index, token):
                index += 1
                continue
            return index
        index += 1
    return -1


def _parse_inline_markdown(text: str, active_marks: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    buffer: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            buffer.append(text[index + 1])
            index += 2
            continue

        matched = False
        for token, token_marks in INLINE_MARKERS:
            if not text.startswith(token, index):
                continue
            if token.startswith("_") and _underscore_token_is_word_internal(text, index, token):
                continue
            closing_index = _find_closing_inline_token(text, token, index + len(token))
            inner_text = text[index + len(token):closing_index] if closing_index >= 0 else ""
            if closing_index < 0 or not inner_text:
                continue
            if buffer:
                _append_inline_text(nodes, "".join(buffer), active_marks)
                buffer = []
            nodes.extend(_parse_inline_markdown(inner_text, _merged_mark_types(active_marks, token_marks)))
            index = closing_index + len(token)
            matched = True
            break
        if matched:
            continue

        buffer.append(text[index])
        index += 1

    if buffer:
        _append_inline_text(nodes, "".join(buffer), active_marks)
    return nodes


def inline_nodes(value: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return _parse_inline_markdown(value)
    if not isinstance(value, list):
        return []

    nodes: list[dict[str, Any]] = []
    for node in value:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "text":
            _append_inline_text(nodes, node.get("text", ""), node.get("marks"))
            continue
        for child in inline_nodes(node.get("content", [])):
            _append_inline_text(nodes, child.get("text", ""), child.get("marks"))
    return nodes


def paragraph_node(text: str | list[dict[str, Any]]) -> dict[str, Any]:
    content = inline_nodes(text)
    return {"type": "paragraph", "content": content} if content else {"type": "paragraph", "content": []}


def heading_node(text: str | list[dict[str, Any]], level: int) -> dict[str, Any]:
    normalized_level = max(1, min(int(level or 1), 6))
    content = inline_nodes(text)
    return {
        "type": "heading",
        "attrs": {"level": normalized_level},
        "content": content,
    }


def list_item_node(
    text: str | list[dict[str, Any]] = "",
    *,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    paragraph_content = inline_nodes(text)
    if paragraph_content or not children:
        content.append(paragraph_node(paragraph_content))
    content.extend(children or [])
    return {"type": "listItem", "content": content}


def bullet_list_node(items: list[str] | list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            list_item_node(item)
            if isinstance(item, str)
            else item
            for item in items
            if (item.strip() if isinstance(item, str) else isinstance(item, dict))
        ],
    }


def ordered_list_node(items: list[str] | list[dict[str, Any]], *, start: int = 1) -> dict[str, Any]:
    normalized_start = max(int(start or 1), 1)
    return {
        "type": "orderedList",
        "attrs": {"start": normalized_start},
        "content": [
            list_item_node(item)
            if isinstance(item, str)
            else item
            for item in items
            if (item.strip() if isinstance(item, str) else isinstance(item, dict))
        ],
    }


def _inline_text_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    return "".join(_inline_text_from_node(item) for item in node.get("content", []))


def _escape_inline_markdown_text(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
    )


def _inline_markdown_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        text = _escape_inline_markdown_text(node.get("text", ""))
        mark_types = set(_normalized_mark_types(node.get("marks")))
        if {"bold", "italic"}.issubset(mark_types):
            return f"***{text}***"
        if "bold" in mark_types:
            return f"**{text}**"
        if "italic" in mark_types:
            return f"*{text}*"
        return text
    return "".join(_inline_markdown_from_node(item) for item in node.get("content", []))


def plain_text_from_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type in {"paragraph", "heading"}:
        return "".join(plain_text_from_node(item) for item in node.get("content", []))
    if node_type == "listItem":
        parts = [plain_text_from_node(item).strip() for item in node.get("content", [])]
        return "\n".join(part for part in parts if part)
    if node_type in {"bulletList", "orderedList"}:
        lines = []
        start = max(int(node.get("attrs", {}).get("start", 1) or 1), 1)
        for index, item in enumerate(node.get("content", []), start=start):
            value = plain_text_from_node(item).strip()
            if value:
                marker = f"{index}." if node_type == "orderedList" else "-"
                item_lines = [line.strip() for line in value.splitlines() if line.strip()]
                if not item_lines:
                    continue
                lines.append(f"{marker} {item_lines[0]}")
                lines.extend(f"  {line}" for line in item_lines[1:])
        return "\n".join(lines)
    return "".join(plain_text_from_node(item) for item in node.get("content", []))


def section_plain_text(section: dict[str, Any]) -> str:
    blocks = section.get("content", []) if isinstance(section, dict) else []
    parts = [plain_text_from_node(block).strip() for block in blocks]
    return "\n\n".join(part for part in parts if part)


def _normalized_heading_key(value: str) -> str:
    candidate = re.sub(r"^\s{0,3}#{1,6}\s*", "", (value or "").strip())
    return slugify(candidate.rstrip(":").strip())


def strip_redundant_section_heading(text: str, title: str) -> str:
    value = (text or "").strip()
    normalized_title = _normalized_heading_key(title)
    if not value or not normalized_title:
        return value

    lines = value.splitlines()
    index = 0
    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines) or _normalized_heading_key(lines[index]) != normalized_title:
            break
        index += 1
    return "\n".join(lines[index:]).strip()


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _next_non_blank_index(lines: list[str], start_index: int) -> int:
    index = start_index
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _parse_paragraph(lines: list[str], start_index: int, *, current_indent: int) -> tuple[dict[str, Any], int]:
    parts: list[str] = []
    index = start_index
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if HEADING_PATTERN.match(line) and _line_indent(line) <= current_indent:
            break
        list_match = LIST_ITEM_PATTERN.match(line)
        if list_match and _line_indent(line) <= current_indent:
            break
        if current_indent and _line_indent(line) <= current_indent and parts:
            break
        parts.append(line.strip())
        index += 1
    return paragraph_node(" ".join(part for part in parts if part).strip()), index


def _parse_list(lines: list[str], start_index: int, current_indent: int) -> tuple[dict[str, Any], int]:
    first_match = LIST_ITEM_PATTERN.match(lines[start_index])
    if not first_match:
        return paragraph_node(lines[start_index].strip()), start_index + 1

    is_ordered = first_match.group(2).endswith(".")
    start_number = int(first_match.group(2)[:-1]) if is_ordered else 1
    items: list[dict[str, Any]] = []
    index = start_index
    while index < len(lines):
        index = _next_non_blank_index(lines, index)
        if index >= len(lines):
            break
        match = LIST_ITEM_PATTERN.match(lines[index])
        if not match or _line_indent(lines[index]) != current_indent:
            break
        if match.group(2).endswith(".") != is_ordered:
            break

        body_parts = [match.group(3).strip()] if match.group(3).strip() else []
        index += 1
        children: list[dict[str, Any]] = []

        while index < len(lines):
            if not lines[index].strip():
                next_index = _next_non_blank_index(lines, index)
                if next_index >= len(lines):
                    index = next_index
                    break
                next_match = LIST_ITEM_PATTERN.match(lines[next_index])
                next_indent = _line_indent(lines[next_index])
                if next_match and next_indent == current_indent:
                    index = next_index
                    break
                if next_match and next_indent > current_indent:
                    index = next_index
                    nested_list, index = _parse_list(lines, index, next_indent)
                    children.append(nested_list)
                    continue
                if next_indent <= current_indent:
                    index = next_index
                    break
                body_parts.append(lines[next_index].strip())
                index = next_index + 1
                continue

            next_match = LIST_ITEM_PATTERN.match(lines[index])
            next_indent = _line_indent(lines[index])
            if next_match and next_indent == current_indent:
                break
            if next_match and next_indent > current_indent:
                nested_list, index = _parse_list(lines, index, next_indent)
                children.append(nested_list)
                continue
            if next_indent <= current_indent:
                break
            body_parts.append(lines[index].strip())
            index += 1

        items.append(list_item_node(" ".join(part for part in body_parts if part).strip(), children=children))

    list_factory = ordered_list_node if is_ordered else bullet_list_node
    if is_ordered:
        return list_factory(items, start=start_number), index
    return list_factory(items), index


def markdown_to_blocks(text: str) -> list[dict[str, Any]]:
    value = (text or "").strip()
    if not value:
        return [paragraph_node("")]

    blocks: list[dict[str, Any]] = []
    lines = [line.rstrip() for line in value.splitlines()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            blocks.append(heading_node(heading_match.group(2).strip(), len(heading_match.group(1))))
            index += 1
            continue

        list_match = LIST_ITEM_PATTERN.match(line)
        if list_match:
            block, index = _parse_list(lines, index, _line_indent(line))
            blocks.append(block)
            continue

        block, index = _parse_paragraph(lines, index, current_indent=0)
        blocks.append(block)

    return blocks or [paragraph_node("")]


def _markdown_lines_from_list_item(
    item: dict[str, Any],
    *,
    indent: int,
    marker: str,
) -> list[str]:
    content = item.get("content", [])
    paragraph = next((child for child in content if child.get("type") == "paragraph"), None)
    nested_children = [child for child in content if child.get("type") in {"bulletList", "orderedList"}]
    other_children = [
        child
        for child in content
        if child.get("type") not in {"paragraph", "bulletList", "orderedList"}
    ]
    first_line = _inline_markdown_from_node(paragraph or {}).strip()
    lines = [f"{' ' * indent}{marker} {first_line}".rstrip()]
    for child in nested_children:
        child_markdown = _markdown_from_block(child, indent=indent + 2)
        if child_markdown:
            lines.extend(child_markdown.splitlines())
    for child in other_children:
        child_text = _inline_markdown_from_node(child).strip()
        if child_text:
            lines.append(f"{' ' * (indent + 2)}{child_text}")
    return lines


def _markdown_from_block(block: dict[str, Any], *, indent: int = 0) -> str:
    node_type = block.get("type")
    if node_type == "paragraph":
        return _inline_markdown_from_node(block).strip()
    if node_type == "heading":
        level = max(int(block.get("attrs", {}).get("level", 1) or 1), 1)
        return f"{'#' * min(level, 6)} {_inline_markdown_from_node(block).strip()}".rstrip()
    if node_type in {"bulletList", "orderedList"}:
        start = max(int(block.get("attrs", {}).get("start", 1) or 1), 1)
        lines: list[str] = []
        for offset, item in enumerate(block.get("content", [])):
            marker = f"{start + offset}." if node_type == "orderedList" else "-"
            lines.extend(_markdown_lines_from_list_item(item, indent=indent, marker=marker))
        return "\n".join(lines)
    return _inline_markdown_from_node(block).strip()


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    parts = [_markdown_from_block(block).strip() for block in blocks or []]
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
        "content": markdown_to_blocks(strip_redundant_section_heading(body, title)),
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
    title = attrs.get("title", "Untitled Section")
    return {
        "id": attrs.get("id", ""),
        "key": attrs.get("key", ""),
        "title": title,
        "kind": attrs.get("kind", DocumentType.CUSTOM),
        "status": attrs.get("status", DocumentStatus.ITERATING),
        "required": bool(attrs.get("required", False)),
        "legacy_slug": attrs.get("legacy_slug", attrs.get("key", "")),
        "body": strip_redundant_section_heading(blocks_to_markdown(section.get("content", [])), title),
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
    title = section_attrs(section).get("title", "")
    return strip_redundant_section_heading(blocks_to_markdown(section.get("content", [])), title)


def section_status_from_ref(content_json: dict[str, Any] | None, primary_ref: dict[str, Any] | None) -> str:
    if not isinstance(primary_ref, dict):
        return DocumentStatus.ITERATING
    section = find_section(content_json, primary_ref.get("section_id", ""))
    if not section:
        return DocumentStatus.ITERATING
    return section_attrs(section).get("status", DocumentStatus.ITERATING)
