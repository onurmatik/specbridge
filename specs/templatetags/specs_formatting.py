from __future__ import annotations

from django import template
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


def _normalized_mark_types(node) -> list[str]:
    if not isinstance(node, dict):
        return []
    normalized: list[str] = []
    for mark in node.get("marks", []) or []:
        mark_type = mark.get("type") if isinstance(mark, dict) else str(mark or "")
        if mark_type in {"bold", "italic"} and mark_type not in normalized:
            normalized.append(mark_type)
    return normalized


def _diff_line_class(line: str) -> str:
    if line.startswith("--- "):
        return "diff-line diff-line-meta-old"
    if line.startswith("+++ "):
        return "diff-line diff-line-meta-new"
    if line.startswith("@@"):
        return "diff-line diff-line-hunk"
    if line.startswith("+"):
        return "diff-line diff-line-add"
    if line.startswith("-"):
        return "diff-line diff-line-remove"
    return "diff-line diff-line-context"


@register.filter
def render_unified_diff(value):
    lines = str(value or "").splitlines()
    if not lines:
        return ""
    return format_html_join(
        "\n",
        '<span class="{}">{}</span>',
        ((_diff_line_class(line), line or "\u200b") for line in lines),
    )


def _render_spec_inline(node) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        rendered = conditional_escape(node.get("text", ""))
        mark_types = set(_normalized_mark_types(node))
        if "italic" in mark_types:
            rendered = format_html("<em>{}</em>", rendered)
        if "bold" in mark_types:
            rendered = format_html("<strong>{}</strong>", rendered)
        return rendered
    return mark_safe("".join(_render_spec_inline(item) for item in node.get("content", [])))


def _render_spec_list_item(node) -> str:
    if not isinstance(node, dict):
        return ""
    content = node.get("content", [])
    paragraph = next((child for child in content if child.get("type") == "paragraph"), None)
    nested_lists = [child for child in content if child.get("type") in {"bulletList", "orderedList"}]
    other_children = [
        child
        for child in content
        if child.get("type") not in {"paragraph", "bulletList", "orderedList"}
    ]
    fragments: list[str] = []
    if paragraph:
        text = _render_spec_inline(paragraph)
        if text:
            fragments.append(str(text))
    for child in nested_lists:
        fragments.append(str(_render_spec_block(child)))
    for child in other_children:
        fragments.append(str(_render_spec_block(child)))
    return format_html("<li>{}</li>", mark_safe("".join(fragments)))


def _render_spec_block(node) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "paragraph":
        return format_html("<p>{}</p>", _render_spec_inline(node))
    if node_type == "heading":
        level = max(min(int(node.get("attrs", {}).get("level", 2) or 2), 6), 1)
        return format_html(f"<h{level}>{{}}</h{level}>", _render_spec_inline(node))
    if node_type in {"bulletList", "orderedList"}:
        tag = "ol" if node_type == "orderedList" else "ul"
        inner = mark_safe("".join(_render_spec_list_item(item) for item in node.get("content", [])))
        return format_html(f"<{tag}>{{}}</{tag}>", inner)
    if node_type == "listItem":
        return _render_spec_list_item(node)
    inline = _render_spec_inline(node)
    return format_html("<p>{}</p>", inline) if inline else ""


@register.filter
def render_spec_blocks(value):
    blocks = value if isinstance(value, list) else []
    if not blocks:
        return ""
    return mark_safe("".join(str(_render_spec_block(block)) for block in blocks))
