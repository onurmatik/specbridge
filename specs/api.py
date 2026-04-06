from django.http import JsonResponse
from ninja import Router, Schema
from ninja.security import django_auth

from projects.services import get_project_or_404, resolve_actor
from specs.concerns import (
    ConcernError,
    accept_concern_proposal_change,
    dismiss_concern,
    ordered_concerns,
    re_evaluate_concern,
    reject_concern_proposal_change,
    render_proposal_change_diff,
    resolve_concern_with_ai,
    run_project_concerns,
)
from specs.consistency import dismiss_consistency_issue, resolve_consistency_issue, run_project_consistency
from specs.models import Assumption, AssumptionStatus, AuditEventType
from specs.section_ai import SectionRevisionError, revise_section_with_ai
from specs.services import (
    add_spec_section_after,
    build_primary_ref_for_section,
    build_project_snapshot,
    build_spec_snapshot,
    capture_project_revision,
    delete_spec_section,
    ensure_spec_document,
    log_audit_event,
    reorder_spec_section,
    update_spec_section,
)
from specs.spec_document import markdown_to_blocks

router = Router(tags=["specs"])


class SpecSectionUpdatePayload(Schema):
    title: str | None = None
    status: str | None = None
    body: str | None = None
    content_json: list[dict] | None = None


class SpecSectionAiRevisionPayload(Schema):
    prompt: str | None = None
    action: str | None = None
    title: str | None = None
    body: str | None = None


class SpecSectionCreatePayload(Schema):
    title: str | None = None


class SpecSectionMovePayload(Schema):
    direction: str


class AssumptionPayload(Schema):
    title: str
    description: str
    section_id: str | None = None
    impact: str = "medium"


def _serialize_sections(project):
    return [
        {
            "id": section["id"],
            "title": section["title"],
            "kind": section["kind"],
            "status": section["status"],
            "required": section["required"],
        }
        for section in build_spec_snapshot(project)["sections"]
    ]


def serialize_concern(concern):
    return {
        "id": concern.id,
        "fingerprint": concern.fingerprint,
        "title": concern.title,
        "summary": concern.summary,
        "concern_type": concern.concern_type,
        "raised_by_kind": concern.raised_by_kind,
        "severity": concern.severity,
        "status": concern.status,
        "recommendation": concern.recommendation,
        "source_refs": concern.source_refs,
        "node_refs": concern.node_refs or [],
        "detected_at": concern.detected_at.isoformat(),
        "last_seen_at": concern.last_seen_at.isoformat(),
        "reevaluation_requested_at": concern.reevaluation_requested_at.isoformat() if concern.reevaluation_requested_at else None,
        "last_reevaluated_at": concern.last_reevaluated_at.isoformat() if concern.last_reevaluated_at else None,
    }


def serialize_proposal(proposal):
    return {
        "id": proposal.id,
        "status": proposal.status,
        "summary": proposal.summary,
        "provider": proposal.provider,
        "model": proposal.model,
        "created_at": proposal.created_at.isoformat(),
        "changes": [
            {
                "id": change.id,
                "section_ref": change.section_ref,
                "section_id": change.section_id,
                "section_title": change.section_title,
                "summary": change.summary,
                "status": change.status,
                "diff": render_proposal_change_diff(change),
                "created_at": change.created_at.isoformat(),
            }
            for change in proposal.changes.all()
        ],
    }


@router.get("/{slug}/spec")
def get_spec(request, slug: str):
    project = get_project_or_404(slug, request.user)
    snapshot = build_spec_snapshot(project)
    return {
        "id": snapshot["id"],
        "title": snapshot["title"],
        "schema_version": snapshot["schema_version"],
        "content_json": snapshot["content_json"],
        "sections": _serialize_sections(project),
    }


@router.patch("/{slug}/spec/sections/{section_id}", auth=django_auth)
def patch_spec_section(request, slug: str, section_id: str, payload: SpecSectionUpdatePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        update_spec_section(
            project=project,
            section_id=section_id,
            actor=actor,
            title=payload.title,
            status=payload.status,
            content_json=payload.content_json if payload.content_json is not None else (
                markdown_to_blocks(payload.body) if payload.body is not None else None
            ),
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "errors": {"section": [str(exc)]}}, status=404)
    return {"ok": True, "section_id": section_id}


@router.post("/{slug}/spec/sections/{section_id}/insert-below", auth=django_auth)
def create_spec_section_below(request, slug: str, section_id: str, payload: SpecSectionCreatePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        section = add_spec_section_after(
            project=project,
            after_section_id=section_id,
            actor=actor,
            title=payload.title or "New Section",
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "errors": {"section": [str(exc)]}}, status=404)
    return {"ok": True, "section_id": section["id"], "title": section["title"]}


@router.post("/{slug}/spec/sections/{section_id}/move", auth=django_auth)
def move_spec_section(request, slug: str, section_id: str, payload: SpecSectionMovePayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        section = reorder_spec_section(
            project=project,
            section_id=section_id,
            direction=payload.direction,
            actor=actor,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Section not found." else 422
        return JsonResponse({"ok": False, "errors": {"section": [str(exc)]}}, status=status_code)
    return {"ok": True, "section_id": section["id"], "direction": payload.direction}


@router.delete("/{slug}/spec/sections/{section_id}", auth=django_auth)
def destroy_spec_section(request, slug: str, section_id: str):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        result = delete_spec_section(project=project, section_id=section_id, actor=actor)
    except ValueError as exc:
        status_code = 404 if str(exc) == "Section not found." else 422
        return JsonResponse({"ok": False, "errors": {"section": [str(exc)]}}, status=status_code)
    return {
        "ok": True,
        "deleted_section_id": result["deleted_section"]["id"],
        "focus_section_id": result["focus_section_id"],
    }


@router.post("/{slug}/spec/sections/{section_id}/revise-with-ai", auth=django_auth)
def revise_spec_section_with_ai(request, slug: str, section_id: str, payload: SpecSectionAiRevisionPayload):
    project = get_project_or_404(slug, request.user)
    try:
        result = revise_section_with_ai(
            project=project,
            section_id=section_id,
            prompt=payload.prompt,
            action=payload.action,
            title=payload.title,
            body=payload.body,
        )
    except SectionRevisionError as exc:
        status_code = 404 if str(exc) == "Section not found." else 422
        return JsonResponse({"ok": False, "errors": {"section": [str(exc)]}}, status=status_code)
    return {
        "ok": True,
        "section_id": section_id,
        "prompt": result.prompt,
        "summary": result.summary,
        "body": result.revised_body,
    }


@router.get("/{slug}/spec/revisions")
def list_spec_revisions(request, slug: str):
    project = get_project_or_404(slug, request.user)
    spec_document = ensure_spec_document(project)
    return {
        "items": [
            {
                "id": revision.id,
                "number": revision.number,
                "title": revision.title,
                "summary": revision.summary,
                "created_at": revision.created_at.isoformat(),
            }
            for revision in spec_document.revisions.order_by("-number")
        ]
    }


@router.post("/{slug}/assumptions", auth=django_auth)
def create_assumption(request, slug: str, payload: AssumptionPayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    primary_ref = build_primary_ref_for_section(project, payload.section_id or "") if payload.section_id else {}
    assumption = Assumption.objects.create(
        project=project,
        title=payload.title,
        description=payload.description,
        impact=payload.impact,
        primary_ref=primary_ref,
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
        metadata={"assumption_id": assumption.id, "section_id": primary_ref.get("section_id", "")},
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


@router.get("/{slug}/concerns")
def list_concerns(request, slug: str):
    project = get_project_or_404(slug, request.user)
    latest_run = project.concern_runs.first()
    return {
        "latest_run": {
            "id": latest_run.id,
            "status": latest_run.status,
            "provider": latest_run.provider,
            "model": latest_run.model,
            "error_message": latest_run.error_message,
            "concern_count": latest_run.concern_count,
            "analyzed_at": latest_run.analyzed_at.isoformat(),
        }
        if latest_run
        else None,
        "items": [serialize_concern(concern) for concern in ordered_concerns(project)],
    }


@router.get("/{slug}/concerns/{concern_id}")
def get_concern(request, slug: str, concern_id: int):
    project = get_project_or_404(slug, request.user)
    concern = project.concerns.prefetch_related("proposals__changes", "posts").get(pk=concern_id)
    return {
        "concern": serialize_concern(concern),
        "posts": [
            {
                "id": post.id,
                "actor_name": post.actor_name,
                "actor_title": post.actor_title,
                "body": post.body,
                "kind": post.kind,
                "created_at": post.created_at.isoformat(),
            }
            for post in concern.posts.all()
        ],
        "proposals": [serialize_proposal(proposal) for proposal in concern.proposals.prefetch_related("changes").all()],
    }


@router.post("/{slug}/concern-runs", auth=django_auth)
def create_concern_run(request, slug: str):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    run = run_project_concerns(project, actor=actor)
    return {"id": run.id, "status": run.status, "concern_count": run.concern_count, "error_message": run.error_message}


@router.post("/{slug}/concerns/{concern_id}/re-evaluate", auth=django_auth)
def re_evaluate_concern_endpoint(request, slug: str, concern_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    concern = project.concerns.get(pk=concern_id)
    run = re_evaluate_concern(concern, actor=actor)
    concern.refresh_from_db()
    return {"ok": True, "status": concern.status, "run_status": run.status}


@router.post("/{slug}/concerns/{concern_id}/resolve-with-ai", auth=django_auth)
def resolve_concern_with_ai_endpoint(request, slug: str, concern_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    concern = project.concerns.get(pk=concern_id)
    try:
        proposal = resolve_concern_with_ai(concern, actor=actor)
    except ConcernError as exc:
        return JsonResponse({"ok": False, "errors": {"concern": [str(exc)]}}, status=422)
    return {"ok": True, "proposal_id": proposal.id, "status": proposal.status}


@router.post("/{slug}/concerns/{concern_id}/dismiss", auth=django_auth)
def dismiss_concern_endpoint(request, slug: str, concern_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    concern = project.concerns.get(pk=concern_id)
    dismiss_concern(concern, actor=actor)
    return {"ok": True, "status": concern.status}


@router.get("/{slug}/concerns/{concern_id}/proposals")
def list_concern_proposals(request, slug: str, concern_id: int):
    project = get_project_or_404(slug, request.user)
    concern = project.concerns.get(pk=concern_id)
    return {
        "items": [
            serialize_proposal(proposal)
            for proposal in concern.proposals.prefetch_related("changes").all()
        ]
    }


@router.post("/{slug}/concern-proposals/{proposal_id}/changes/{change_id}/accept", auth=django_auth)
def accept_concern_proposal_change_endpoint(request, slug: str, proposal_id: int, change_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    proposal = project.concern_proposals.get(pk=proposal_id)
    change = proposal.changes.select_related("proposal__concern").get(pk=change_id)
    accept_concern_proposal_change(change, actor=actor)
    return {"ok": True, "status": change.status}


@router.post("/{slug}/concern-proposals/{proposal_id}/changes/{change_id}/reject", auth=django_auth)
def reject_concern_proposal_change_endpoint(request, slug: str, proposal_id: int, change_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    proposal = project.concern_proposals.get(pk=proposal_id)
    change = proposal.changes.select_related("proposal__concern").get(pk=change_id)
    reject_concern_proposal_change(change, actor=actor)
    return {"ok": True, "status": change.status}


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
