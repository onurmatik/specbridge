import json

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, JsonResponse
from ninja import Router, Schema
from ninja.security import django_auth

from alignment.models import Decision, OpenQuestion, StreamPost
from alignment.stream_attachments import (
    StreamAttachmentValidationError,
    create_pending_attachments_for_post,
    process_stream_post_upload,
    serialize_stream_attachment,
    set_post_processing_state,
    touch_project_activity,
    validate_stream_uploads,
)
from alignment.services import approve_decision, mark_decision_implemented, reject_decision, reopen_issue, resolve_issue
from projects.services import get_project_or_404, resolve_actor
from specs.concerns import create_human_concern_from_post
from specs.services import build_primary_ref_for_section

router = Router(tags=["alignment"])


class StreamPayload(Schema):
    body: str
    concern_id: int | None = None


class DecisionPayload(Schema):
    title: str
    summary: str
    section_id: str = ""


def _serialize_stream_post(post: StreamPost) -> dict:
    attachments = list(post.attachments.all())
    return {
        "id": post.id,
        "actor_name": post.actor_name,
        "actor_title": post.actor_title,
        "kind": post.kind,
        "concern_id": post.concern_id,
        "body": post.body,
        "processing_status": post.processing_status,
        "processing_error": post.processing_error,
        "created_at": post.created_at.isoformat(),
        "attachments": [serialize_stream_attachment(attachment) for attachment in attachments],
    }


def _request_payload(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            raise StreamAttachmentValidationError({"body": ["Request body must be valid JSON."]})
    return request.POST


@router.get("/{slug}/stream")
def list_stream(request, slug: str):
    project = get_project_or_404(slug, request.user)
    return {
        "items": [
            _serialize_stream_post(post)
            for post in project.stream_posts.prefetch_related("attachments").all()
        ]
    }


@router.post("/{slug}/stream", auth=django_auth)
def create_stream_post(request, slug: str):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        payload = _request_payload(request)
        uploaded_files = request.FILES.getlist("files")
        validate_stream_uploads(uploaded_files)
    except StreamAttachmentValidationError as exc:
        return JsonResponse({"ok": False, "errors": exc.errors}, status=422)

    body = str(payload.get("body") or "").strip()
    if not body and not uploaded_files:
        return JsonResponse({"ok": False, "errors": {"body": ["Message is required."]}}, status=422)

    concern_id = payload.get("concern_id")
    concern = project.concerns.filter(pk=concern_id).first() if concern_id else None
    post = StreamPost.objects.create(
        project=project,
        author=actor,
        actor_name=actor.display_name,
        actor_title=actor.title,
        concern=concern,
        body=body,
    )
    touch_project_activity(project)
    attachments = create_pending_attachments_for_post(post, uploaded_files)
    if attachments:
        set_post_processing_state(post, "pending")

    post = project.stream_posts.prefetch_related("attachments").get(pk=post.pk)
    response_payload = _serialize_stream_post(post)
    response_payload.update(
        {
            "processing_pending": bool(attachments),
            "processing_url": f"/api/projects/{project.slug}/stream/{post.id}/process-files" if attachments else "",
        }
    )
    return response_payload


@router.post("/{slug}/stream/{post_id}/promote-to-concern", auth=django_auth)
def promote_stream_post_to_concern(request, slug: str, post_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    post = project.stream_posts.get(pk=post_id)
    concern = create_human_concern_from_post(post, actor=actor)
    return {"ok": True, "concern_id": concern.id}


@router.post("/{slug}/stream/{post_id}/process-files", auth=django_auth)
def process_stream_post_files(request, slug: str, post_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    post = project.stream_posts.prefetch_related("attachments").filter(pk=post_id).first()
    if not post:
        return JsonResponse({"ok": False, "errors": {"post": ["Post not found."]}}, status=404)
    if not post.attachments.exists():
        return {"ok": True, "status": post.processing_status}
    result = process_stream_post_upload(post, actor=actor)
    post.refresh_from_db()
    return {
        "ok": True,
        "status": post.processing_status,
        "processing_error": post.processing_error,
        "agent_post_id": result.agent_post.id if result.agent_post else None,
    }


@router.get("/{slug}/files/{attachment_id}/download")
def download_stream_attachment(request, slug: str, attachment_id: int):
    project = get_project_or_404(slug, request.user)
    try:
        resolve_actor(request, project)
    except PermissionDenied as exc:
        return JsonResponse({"ok": False, "errors": {"auth": [str(exc)]}}, status=403)
    attachment = project.stream_attachments.filter(pk=attachment_id).first()
    if not attachment:
        return JsonResponse({"ok": False, "errors": {"file": ["File not found."]}}, status=404)
    response = FileResponse(
        attachment.stored_file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
    )
    if attachment.content_type:
        response["Content-Type"] = attachment.content_type
    return response


@router.post("/{slug}/questions/{question_id}/resolve", auth=django_auth)
def resolve_question(request, slug: str, question_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    question = project.questions.get(pk=question_id)
    resolve_issue(question, actor)
    return {"ok": True, "status": question.status}


@router.post("/{slug}/questions/{question_id}/reopen", auth=django_auth)
def reopen_question(request, slug: str, question_id: int):
    project = get_project_or_404(slug, request.user)
    question = project.questions.get(pk=question_id)
    reopen_issue(question)
    return {"ok": True, "status": question.status}


@router.post("/{slug}/blockers/{blocker_id}/resolve", auth=django_auth)
def resolve_blocker(request, slug: str, blocker_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    blocker = project.blockers.get(pk=blocker_id)
    resolve_issue(blocker, actor)
    return {"ok": True, "status": blocker.status}


@router.post("/{slug}/blockers/{blocker_id}/reopen", auth=django_auth)
def reopen_blocker(request, slug: str, blocker_id: int):
    project = get_project_or_404(slug, request.user)
    blocker = project.blockers.get(pk=blocker_id)
    reopen_issue(blocker)
    return {"ok": True, "status": blocker.status}


@router.post("/{slug}/decisions", auth=django_auth)
def create_decision(request, slug: str, payload: DecisionPayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    primary_ref = build_primary_ref_for_section(project, payload.section_id) if payload.section_id else {}
    decision = Decision.objects.create(
        project=project,
        title=payload.title,
        summary=payload.summary,
        proposed_by=actor,
        primary_ref=primary_ref,
    )
    return {"id": decision.id, "code": decision.code, "title": decision.title, "status": decision.status}


@router.post("/{slug}/decisions/{decision_id}/approve", auth=django_auth)
def approve_decision_endpoint(request, slug: str, decision_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    decision = project.decisions.get(pk=decision_id)
    approve_decision(decision, actor)
    return {"ok": True, "status": decision.status}


@router.post("/{slug}/decisions/{decision_id}/reject", auth=django_auth)
def reject_decision_endpoint(request, slug: str, decision_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    decision = project.decisions.get(pk=decision_id)
    reject_decision(decision, actor)
    return {"ok": True, "status": decision.status}


@router.post("/{slug}/decisions/{decision_id}/mark-implemented", auth=django_auth)
def mark_implemented_endpoint(request, slug: str, decision_id: int):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    decision = project.decisions.get(pk=decision_id)
    mark_decision_implemented(decision, actor)
    return {"ok": True, "status": decision.status}
