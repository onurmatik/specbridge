from __future__ import annotations

from typing import Any

from django.utils.text import slugify

from specs.models import (
    AuditEvent,
    AuditEventType,
    DocumentRevision,
    DocumentSourceKind,
    DocumentStatus,
    DocumentType,
    ProjectDocument,
    ProjectRevision,
)

DEFAULT_DOCUMENT_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "slug": "overview",
        "title": "Overview",
        "document_type": DocumentType.OVERVIEW,
        "source_kind": DocumentSourceKind.PRESET,
        "is_required": False,
    },
)

DOCUMENT_SUGGESTIONS: tuple[dict[str, Any], ...] = (
    {
        "slug": "overview",
        "title": "Overview",
        "document_type": DocumentType.OVERVIEW,
    },
    {
        "slug": "goals",
        "title": "Goals",
        "document_type": DocumentType.GOALS,
    },
    {
        "slug": "requirements",
        "title": "Requirements",
        "document_type": DocumentType.REQUIREMENTS,
    },
    {
        "slug": "ui-ux",
        "title": "UI/UX",
        "document_type": DocumentType.UI_UX,
    },
    {
        "slug": "tech-stack",
        "title": "Tech Stack",
        "document_type": DocumentType.TECH_STACK,
    },
    {
        "slug": "infra",
        "title": "Infra",
        "document_type": DocumentType.INFRA,
    },
    {
        "slug": "risks-open-questions",
        "title": "Risks & Open Questions",
        "document_type": DocumentType.RISKS_OPEN_QUESTIONS,
    },
)


def build_document_snapshot(document: ProjectDocument) -> dict[str, Any]:
    return {
        "slug": document.slug,
        "title": document.title,
        "document_type": document.document_type,
        "source_kind": document.source_kind,
        "body": document.body,
        "status": document.status,
        "order": document.order,
        "is_required": document.is_required,
    }


def build_project_snapshot(project) -> dict[str, Any]:
    documents = [
        build_document_snapshot(document)
        for document in project.documents.all()
    ]
    decisions = [
        {
            "id": decision.id,
            "code": decision.code,
            "title": decision.title,
            "summary": decision.summary,
            "status": decision.status,
            "related_document_slug": decision.related_document.slug if decision.related_document else "",
            "related_document_title": decision.related_document.title if decision.related_document else "",
            "implementation_progress": decision.implementation_progress,
        }
        for decision in project.decisions.select_related("related_document").all()
    ]
    assumptions = [
        {
            "id": assumption.id,
            "title": assumption.title,
            "description": assumption.description,
            "status": assumption.status,
            "document_slug": assumption.document.slug if assumption.document else "",
            "document_title": assumption.document.title if assumption.document else "",
            "impact": assumption.impact,
        }
        for assumption in project.assumptions.select_related("document").all()
    ]
    return {
        "project": {
            "id": project.id,
            "slug": project.slug,
            "name": project.name,
            "tagline": project.tagline,
            "summary": project.summary,
        },
        "documents": documents,
        "decisions": decisions,
        "assumptions": assumptions,
    }


def log_audit_event(
    *,
    project,
    event_type: str,
    title: str,
    description: str = "",
    actor=None,
    metadata: dict[str, Any] | None = None,
    source_post=None,
    source_decision=None,
    source_assumption=None,
    source_agent=None,
    project_revision=None,
):
    return AuditEvent.objects.create(
        project=project,
        actor=actor,
        event_type=event_type,
        title=title,
        description=description,
        metadata=metadata or {},
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        project_revision=project_revision,
    )


def capture_project_revision(
    *,
    project,
    title: str,
    summary: str = "",
    actor=None,
    source_post=None,
    source_decision=None,
    source_assumption=None,
    source_agent=None,
):
    previous_revision = project.revisions.order_by("-number").first()
    revision = ProjectRevision.objects.create(
        project=project,
        number=(previous_revision.number + 1) if previous_revision else 1,
        title=title,
        summary=summary,
        snapshot=build_project_snapshot(project),
        created_by=actor,
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        previous_revision=previous_revision,
    )
    log_audit_event(
        project=project,
        event_type=AuditEventType.PROJECT_REVISION_CREATED,
        title=f"Captured {project.name} r{revision.number}",
        description=summary or title,
        actor=actor,
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        project_revision=revision,
        metadata={"revision": revision.number, "title": title},
    )
    return revision


def capture_document_revision(
    *,
    document: ProjectDocument,
    title: str,
    summary: str = "",
    actor=None,
    project_revision: ProjectRevision | None = None,
):
    previous_revision = document.revisions.order_by("-number").first()
    return DocumentRevision.objects.create(
        document=document,
        number=(previous_revision.number + 1) if previous_revision else 1,
        title=title,
        summary=summary,
        snapshot=build_document_snapshot(document),
        created_by=actor,
        project_revision=project_revision,
        previous_revision=previous_revision,
    )


def _next_document_order(project) -> int:
    last_document = project.documents.order_by("-order", "-created_at").first()
    return (last_document.order + 1) if last_document else 1


def unique_document_slug(project, title: str, *, seed: str | None = None) -> str:
    base_slug = slugify(seed or title) or "document"
    slug = base_slug
    suffix = 2
    while project.documents.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def bootstrap_documents(project) -> list[ProjectDocument]:
    documents = [
        ProjectDocument(
            project=project,
            slug=preset["slug"],
            title=preset["title"],
            document_type=preset["document_type"],
            source_kind=preset["source_kind"],
            body="",
            status=DocumentStatus.ITERATING,
            order=index,
            is_required=preset["is_required"],
        )
        for index, preset in enumerate(DEFAULT_DOCUMENT_PRESETS, start=1)
    ]
    ProjectDocument.objects.bulk_create(documents)
    return list(project.documents.order_by("order", "created_at"))


def create_document(
    *,
    project,
    title: str,
    actor=None,
    document_type: str = DocumentType.CUSTOM,
    body: str = "",
    status: str = DocumentStatus.ITERATING,
    is_required: bool = False,
):
    title = (title or "").strip()
    if not title:
        raise ValueError("Document title is required.")
    source_kind = DocumentSourceKind.CUSTOM if document_type == DocumentType.CUSTOM else DocumentSourceKind.PRESET
    document = ProjectDocument.objects.create(
        project=project,
        slug=unique_document_slug(project, title),
        title=title,
        document_type=document_type,
        source_kind=source_kind,
        body=body,
        status=status,
        order=_next_document_order(project),
        is_required=is_required,
    )
    project_revision = capture_project_revision(
        project=project,
        title=f"Document created: {document.title}",
        summary=f"Added {document.title} to the project document set.",
        actor=actor,
    )
    capture_document_revision(
        document=document,
        title=f"Document created: {document.title}",
        summary=document.body[:160],
        actor=actor,
        project_revision=project_revision,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_CREATED,
        title=f"Created document {document.title}",
        description=document.body[:160],
        metadata={"document_slug": document.slug, "document_type": document.document_type},
        project_revision=project_revision,
    )
    return document


def update_document(
    *,
    document: ProjectDocument,
    actor=None,
    title: str | None = None,
    body: str | None = None,
    status: str | None = None,
):
    if title is not None:
        document.title = title
    if body is not None:
        document.body = body
    if status is not None:
        document.status = status
    document.save()
    description = f"Updated document {document.title}"
    project_revision = capture_project_revision(
        project=document.project,
        title=f"Document updated: {document.title}",
        summary=description,
        actor=actor,
    )
    capture_document_revision(
        document=document,
        title=f"Document updated: {document.title}",
        summary=document.body[:160],
        actor=actor,
        project_revision=project_revision,
    )
    log_audit_event(
        project=document.project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_UPDATED,
        title=description,
        description=description,
        metadata={"document_slug": document.slug, "status": document.status},
        project_revision=project_revision,
    )
    return project_revision


def delete_document(*, document: ProjectDocument, actor=None):
    project = document.project
    metadata = {"document_slug": document.slug, "document_type": document.document_type}
    title = document.title
    document.delete()
    project_revision = capture_project_revision(
        project=project,
        title=f"Document deleted: {title}",
        summary=f"Removed {title} from the project document set.",
        actor=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_DELETED,
        title=f"Deleted document {title}",
        metadata=metadata,
        project_revision=project_revision,
    )
    return project_revision


def reorder_documents(*, project, ordered_slugs: list[str], actor=None):
    ordered = {slug: index for index, slug in enumerate(ordered_slugs, start=1)}
    documents = list(project.documents.order_by("order", "created_at"))
    changed = False
    next_order = len(ordered) + 1
    for document in documents:
        desired_order = ordered.get(document.slug)
        if desired_order is None:
            desired_order = next_order
            next_order += 1
        if document.order != desired_order:
            document.order = desired_order
            document.save(update_fields=["order", "updated_at"])
            changed = True
    if not changed:
        return None
    project_revision = capture_project_revision(
        project=project,
        title="Documents reordered",
        summary="Updated the primary document order.",
        actor=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_REORDERED,
        title="Reordered project documents",
        description="Updated the primary document order.",
        metadata={"ordered_slugs": ordered_slugs},
        project_revision=project_revision,
    )
    return project_revision


def compare_document_revisions(left: DocumentRevision, right: DocumentRevision) -> dict[str, Any]:
    return {
        "title_changed": left.snapshot.get("title") != right.snapshot.get("title"),
        "body_changed": left.snapshot.get("body") != right.snapshot.get("body"),
        "status_changed": left.snapshot.get("status") != right.snapshot.get("status"),
        "previous": left.snapshot,
        "current": right.snapshot,
    }
