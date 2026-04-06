from django import template
from django.utils.html import format_html_join

register = template.Library()


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
