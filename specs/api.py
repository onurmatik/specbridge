from ninja import Router, Schema
from ninja.security import django_auth

from projects.services import get_project_or_404, resolve_actor
from specs.consistency import dismiss_consistency_issue, resolve_consistency_issue, run_project_consistency
from specs.models import Assumption, AssumptionStatus, AuditEventType, DocumentStatus, DocumentType
from specs.services import (
    capture_project_revision,
    create_document,
    delete_document,
    log_audit_event,
    reorder_documents,
    update_document,
)

router = Router(tags=["specs"])


class DocumentCreatePayload(Schema):
    title: str
    body: str = ""
    document_type: str = DocumentType.CUSTOM
    status: str = DocumentStatus.ITERATING
    is_required: bool = False


class DocumentUpdatePayload(Schema):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    is_required: bool | None = None


class DocumentReorderPayload(Schema):
    slugs: list[str]


class AssumptionPayload(Schema):
    title: str
    description: str
    document_slug: str | None = None
    impact: str = "medium"


@router.get("/{slug}/documents")
def list_documents(request, slug: str):
    project = get_project_or_404(slug, request.user)
    return {
        "items": [
            {
                "id": document.id,
                "slug": document.slug,
                "title": document.title,
                "body": document.body,
                "status": document.status,
                "document_type": document.document_type,
                "source_kind": document.source_kind,
                "is_required": document.is_required,
                "order": document.order,
            }
            for document in project.documents.all()
        ]
    }


@router.post("/{slug}/documents", auth=django_auth)
def create_document_endpoint(request, slug: str, payload: DocumentCreatePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        document = create_document(
            project=project,
            actor=actor,
            title=payload.title,
            body=payload.body,
            document_type=payload.document_type,
            status=payload.status,
            is_required=payload.is_required,
        )
    except ValueError as exc:
        return 422, {"ok": False, "errors": {"title": [str(exc)]}}
    return {"id": document.id, "slug": document.slug, "status": document.status}


@router.get("/{slug}/documents/{document_slug}")
def get_document(request, slug: str, document_slug: str):
    project = get_project_or_404(slug, request.user)
    document = project.documents.get(slug=document_slug)
    return {
        "id": document.id,
        "slug": document.slug,
        "title": document.title,
        "body": document.body,
        "status": document.status,
        "document_type": document.document_type,
        "source_kind": document.source_kind,
        "order": document.order,
        "is_required": document.is_required,
    }


@router.patch("/{slug}/documents/{document_slug}", auth=django_auth)
def patch_document(request, slug: str, document_slug: str, payload: DocumentUpdatePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    document = project.documents.get(slug=document_slug)
    if payload.is_required is not None:
        document.is_required = payload.is_required
        document.save(update_fields=["is_required", "updated_at"])
    update_document(
        document=document,
        actor=actor,
        title=payload.title,
        body=payload.body,
        status=payload.status,
    )
    return {"ok": True, "document": document.slug, "status": document.status}


@router.delete("/{slug}/documents/{document_slug}", auth=django_auth)
def delete_document_endpoint(request, slug: str, document_slug: str):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    document = project.documents.get(slug=document_slug)
    delete_document(document=document, actor=actor)
    return {"ok": True}


@router.post("/{slug}/documents/reorder", auth=django_auth)
def reorder_documents_endpoint(request, slug: str, payload: DocumentReorderPayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    reorder_documents(project=project, ordered_slugs=payload.slugs, actor=actor)
    return {"ok": True}


@router.get("/{slug}/documents/{document_slug}/revisions")
def list_document_revisions(request, slug: str, document_slug: str):
    project = get_project_or_404(slug, request.user)
    document = project.documents.get(slug=document_slug)
    return {
        "items": [
            {
                "id": revision.id,
                "number": revision.number,
                "title": revision.title,
                "summary": revision.summary,
                "created_at": revision.created_at.isoformat(),
            }
            for revision in document.revisions.order_by("-number")
        ]
    }


@router.post("/{slug}/assumptions", auth=django_auth)
def create_assumption(request, slug: str, payload: AssumptionPayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    document = project.documents.filter(slug=payload.document_slug).first() if payload.document_slug else None
    assumption = Assumption.objects.create(
        project=project,
        document=document,
        title=payload.title,
        description=payload.description,
        impact=payload.impact,
        created_by=actor,
    )
    revision = capture_project_revision(
        project=project,
        title=f"Assumption added: {assumption.title}",
        summary=assumption.description,
        actor=actor,
        source_assumption=assumption,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.ASSUMPTION_CREATED,
        title=f"Added assumption {assumption.title}",
        description=assumption.description,
        source_assumption=assumption,
        project_revision=revision,
        metadata={"assumption_id": assumption.id, "document_slug": document.slug if document else ""},
    )
    return {"id": assumption.id, "status": assumption.status}


@router.post("/{slug}/assumptions/{assumption_id}/validate", auth=django_auth)
def validate_assumption(request, slug: str, assumption_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    assumption = project.assumptions.get(pk=assumption_id)
    assumption.status = AssumptionStatus.VALIDATED
    assumption.validated_by = actor
    assumption.save(update_fields=["status", "validated_by", "updated_at"])
    revision = capture_project_revision(
        project=project,
        title=f"Assumption validated: {assumption.title}",
        summary=assumption.description,
        actor=actor,
        source_assumption=assumption,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.ASSUMPTION_VALIDATED,
        title=f"Validated assumption {assumption.title}",
        description=assumption.description,
        source_assumption=assumption,
        project_revision=revision,
        metadata={"assumption_id": assumption.id},
    )
    return {"ok": True, "status": assumption.status}


@router.post("/{slug}/assumptions/{assumption_id}/invalidate", auth=django_auth)
def invalidate_assumption(request, slug: str, assumption_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    assumption = project.assumptions.get(pk=assumption_id)
    assumption.status = AssumptionStatus.INVALIDATED
    assumption.validated_by = actor
    assumption.save(update_fields=["status", "validated_by", "updated_at"])
    revision = capture_project_revision(
        project=project,
        title=f"Assumption invalidated: {assumption.title}",
        summary=assumption.description,
        actor=actor,
        source_assumption=assumption,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.ASSUMPTION_INVALIDATED,
        title=f"Invalidated assumption {assumption.title}",
        description=assumption.description,
        source_assumption=assumption,
        project_revision=revision,
        metadata={"assumption_id": assumption.id},
    )
    return {"ok": True, "status": assumption.status}


@router.get("/{slug}/project-revisions")
def list_project_revisions(request, slug: str):
    project = get_project_or_404(slug, request.user)
    return {
        "items": [
            {
                "id": revision.id,
                "number": revision.number,
                "title": revision.title,
                "summary": revision.summary,
                "created_at": revision.created_at.isoformat(),
            }
            for revision in project.revisions.order_by("-number")
        ]
    }


@router.get("/{slug}/consistency-issues")
def list_consistency_issues(request, slug: str):
    project = get_project_or_404(slug, request.user)
    latest_run = project.consistency_runs.first()
    return {
        "latest_run": {
            "id": latest_run.id,
            "status": latest_run.status,
            "provider": latest_run.provider,
            "model": latest_run.model,
            "error_message": latest_run.error_message,
            "issue_count": latest_run.issue_count,
            "analyzed_at": latest_run.analyzed_at.isoformat(),
        }
        if latest_run
        else None,
        "items": [
            {
                "id": issue.id,
                "fingerprint": issue.fingerprint,
                "title": issue.title,
                "summary": issue.summary,
                "severity": issue.severity,
                "status": issue.status,
                "source_refs": issue.source_refs,
                "recommendation": issue.recommendation,
                "last_seen_at": issue.last_seen_at.isoformat(),
            }
            for issue in project.consistency_issues.all()
        ],
    }


@router.post("/{slug}/consistency-runs", auth=django_auth)
def create_consistency_run(request, slug: str):
    project = get_project_or_404(slug, request.user)
    resolve_actor(request, project)
    run = run_project_consistency(project)
    return {"id": run.id, "status": run.status, "issue_count": run.issue_count, "error_message": run.error_message}


@router.post("/{slug}/consistency-issues/{issue_id}/resolve", auth=django_auth)
def resolve_consistency_issue_endpoint(request, slug: str, issue_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    issue = project.consistency_issues.get(pk=issue_id)
    resolve_consistency_issue(issue=issue, actor=actor)
    return {"ok": True, "status": issue.status}


@router.post("/{slug}/consistency-issues/{issue_id}/dismiss", auth=django_auth)
def dismiss_consistency_issue_endpoint(request, slug: str, issue_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    issue = project.consistency_issues.get(pk=issue_id)
    dismiss_consistency_issue(issue=issue, actor=actor)
    return {"ok": True, "status": issue.status}
