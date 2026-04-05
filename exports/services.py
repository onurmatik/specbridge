import secrets

from django.utils import timezone

from exports.models import ExportArtifact, ExportFormat
from specs.models import AuditEventType
from specs.services import log_audit_event


def selected_documents_for_export(project, configuration: dict | None = None):
    configuration = configuration or {}
    document_slugs = configuration.get("document_slugs", "")
    if isinstance(document_slugs, str):
        allowed = {slug.strip() for slug in document_slugs.split(",") if slug.strip()}
    elif isinstance(document_slugs, list):
        allowed = {slug for slug in document_slugs if slug}
    else:
        allowed = set()

    documents = list(project.documents.order_by("order", "created_at"))
    if not allowed:
        return documents
    return [document for document in documents if document.slug in allowed]


def build_export_content(project, export_format: str, configuration: dict | None = None) -> str:
    configuration = configuration or {}
    include_resolved_questions = configuration.get("include_resolved_questions", False)
    documents = selected_documents_for_export(project, configuration)
    lines = [
        f"# {project.name}",
        "",
        project.summary,
        "",
        "## Documents",
    ]
    for document in documents:
        lines.extend(
            [
                f"### {document.order}. {document.title}",
                f"- Status: {document.get_status_display()}",
                f"- Type: {document.get_document_type_display()}",
                "",
                document.body or "_No content yet._",
                "",
            ]
        )
    lines.append("## Decisions")
    for decision in project.decisions.select_related("related_document").all():
        if decision.related_document and decision.related_document not in documents:
            continue
        related_label = f" ({decision.related_document.title})" if decision.related_document else ""
        lines.append(f"- [{decision.status}] {decision.title}{related_label}: {decision.summary}")
    lines.append("")
    lines.append("## Assumptions")
    for assumption in project.assumptions.select_related("document").all():
        if assumption.document and assumption.document not in documents:
            continue
        related_label = f" ({assumption.document.title})" if assumption.document else ""
        lines.append(f"- [{assumption.status}] {assumption.title}{related_label}: {assumption.description}")
    if include_resolved_questions:
        lines.append("")
        lines.append("## Questions")
        for question in project.questions.select_related("related_document").all():
            related_label = f" ({question.related_document.title})" if question.related_document else ""
            lines.append(f"- [{question.status}] {question.title}{related_label}")
    if export_format == ExportFormat.AGENT:
        lines.insert(0, "You are implementing a multi-document project workspace in SpecBridge.")
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
