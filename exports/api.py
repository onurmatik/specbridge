from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from exports.services import create_export, download_url_for_artifact, export_file_type_for_artifact, toggle_share
from projects.services import get_project_or_404, resolve_actor

router = Router(tags=["exports"])


class ExportPayload(Schema):
    format: str
    file_type: str | None = None
    extension: str | None = None
    share_enabled: bool = False
    include_resolved_questions: bool = False
    section_ids: str | None = None


class SharePayload(Schema):
    enabled: bool


@router.get("/{slug}/exports")
def list_exports(request, slug: str):
    project = get_project_or_404(slug, request.user)
    return {
        "items": [
            {
                "id": artifact.id,
                "format": artifact.format,
                "file_type": export_file_type_for_artifact(artifact),
                "title": artifact.title,
                "filename": artifact.filename,
                "status": artifact.status,
                "share_enabled": artifact.share_enabled,
                "share_token": artifact.share_token,
                "download_url": download_url_for_artifact(artifact),
            }
            for artifact in project.exports.all()
        ]
    }


@router.post("/{slug}/exports", auth=django_auth)
def create_export_endpoint(request, slug: str, payload: ExportPayload):
    project = get_project_or_404(slug, request.user)
    actor = resolve_actor(request, project)
    try:
        artifact = create_export(project, payload.format, actor, payload.dict())
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    return {
        "id": artifact.id,
        "file_type": export_file_type_for_artifact(artifact),
        "filename": artifact.filename,
        "status": artifact.status,
        "download_url": download_url_for_artifact(artifact),
    }


@router.post("/{slug}/exports/{export_id}/share-toggle", auth=django_auth)
def toggle_share_endpoint(request, slug: str, export_id: int, payload: SharePayload):
    project = get_project_or_404(slug, request.user)
    artifact = project.exports.get(pk=export_id)
    toggle_share(artifact, payload.enabled)
    return {"ok": True, "share_enabled": artifact.share_enabled}
