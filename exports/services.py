import secrets

from django.utils import timezone

from exports.models import ExportArtifact, ExportFormat
from specs.models import AuditEventType
from specs.services import log_audit_event


def build_export_content(project, export_format: str, configuration: dict | None = None) -> str:
    configuration = configuration or {}
    include_resolved_questions = configuration.get("include_resolved_questions", False)
    lines = [
        f"# {project.name}",
        "",
        project.summary,
        "",
        "## Sections",
    ]
    for section in project.sections.all():
        lines.extend(
            [
                f"### {section.order}. {section.title}",
                section.summary,
                "",
                section.body,
                "",
            ]
        )
    lines.append("## Decisions")
    for decision in project.decisions.all():
        lines.append(f"- [{decision.status}] {decision.title}: {decision.summary}")
    lines.append("")
    lines.append("## Assumptions")
    for assumption in project.assumptions.all():
        lines.append(f"- [{assumption.status}] {assumption.title}: {assumption.description}")
    if include_resolved_questions:
        lines.append("")
        lines.append("## Questions")
        for question in project.questions.all():
            lines.append(f"- [{question.status}] {question.title}")
    if export_format == ExportFormat.AGENT:
        lines.insert(0, "You are implementing SpecBridge.")
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
