import secrets

from django.utils import timezone

from exports.models import ExportArtifact, ExportFormat
from specs.models import AuditEventType
from specs.services import (
    log_audit_event,
    section_summaries,
    section_title_for_ref,
)


def selected_sections_for_export(project, configuration: dict | None = None):
    configuration = configuration or {}
    section_ids = configuration.get("section_ids", "")
    if isinstance(section_ids, str):
        allowed = {section_id.strip() for section_id in section_ids.split(",") if section_id.strip()}
    elif isinstance(section_ids, list):
        allowed = {section_id for section_id in section_ids if section_id}
    else:
        allowed = set()

    sections = list(section_summaries(project))
    if not allowed:
        return sections
    return [section for section in sections if section["id"] in allowed]


def build_export_content(project, export_format: str, configuration: dict | None = None) -> str:
    configuration = configuration or {}
    include_resolved_questions = configuration.get("include_resolved_questions", False)
    sections = selected_sections_for_export(project, configuration)
    allowed_ids = {section["id"] for section in sections}
    lines = [
        f"# {project.name}",
        "",
        project.summary,
        "",
        "## Sections",
    ]
    for index, section in enumerate(sections, start=1):
        lines.extend(
            [
                f"### {index}. {section['title']}",
                f"- Status: {section['status'].replace('-', ' ').title()}",
                f"- Type: {section['kind']}",
                "",
                section["body"] or "_No content yet._",
                "",
            ]
        )
    lines.append("## Decisions")
    for decision in project.decisions.all():
        primary_ref = decision.primary_ref or {}
        if primary_ref.get("section_id") and primary_ref["section_id"] not in allowed_ids:
            continue
        related_label = f" ({section_title_for_ref(project, primary_ref)})" if primary_ref else ""
        lines.append(f"- [{decision.status}] {decision.title}{related_label}: {decision.summary}")
    lines.append("")
    lines.append("## Assumptions")
    for assumption in project.assumptions.all():
        primary_ref = assumption.primary_ref or {}
        if primary_ref.get("section_id") and primary_ref["section_id"] not in allowed_ids:
            continue
        related_label = f" ({section_title_for_ref(project, primary_ref)})" if primary_ref else ""
        lines.append(f"- [{assumption.status}] {assumption.title}{related_label}: {assumption.description}")
    if include_resolved_questions:
        lines.append("")
        lines.append("## Questions")
        for question in project.questions.all():
            primary_ref = question.primary_ref or {}
            if primary_ref.get("section_id") and primary_ref["section_id"] not in allowed_ids:
                continue
            related_label = f" ({section_title_for_ref(project, primary_ref)})" if primary_ref else ""
            lines.append(f"- [{question.status}] {question.title}{related_label}")
    if export_format == ExportFormat.AGENT:
        lines.insert(0, "You are implementing a single spec document workspace in SpecBridge.")
    return "\n".join(lines)


def create_export(project, export_format, actor, configuration=None):
    configuration = configuration or {}
    label = dict(ExportFormat.choices).get(export_format, export_format)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    extension = configuration.get("extension", "md")
    artifact = ExportArtifact.objects.create(
        project=project,
        format=export_format,
        title=f"{label} export",
        filename=f"{project.slug}_{export_format}_{stamp}.{extension}",
        generated_by=actor,
        configuration=configuration,
        content=build_export_content(project, export_format, configuration),
        share_enabled=configuration.get("share_enabled", False),
        share_token=secrets.token_hex(12),
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.EXPORT_CREATED,
        title=f"Generated export: {artifact.filename}",
        description=f"{label} export generated",
        metadata={"export_id": artifact.id, "format": artifact.format},
    )
    return artifact


def toggle_share(artifact, enabled: bool):
    artifact.share_enabled = enabled
    if enabled and not artifact.share_token:
        artifact.share_token = secrets.token_hex(12)
    artifact.save(update_fields=["share_enabled", "share_token", "updated_at"])
    return artifact
