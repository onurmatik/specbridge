from ninja import Router, Schema
from ninja.security import django_auth

from exports.services import create_export, toggle_share
from projects.services import get_project_or_404, resolve_actor

router = Router(tags=["exports"])


class ExportPayload(Schema):
    format: str
    extension: str = "md"
    share_enabled: bool = False
    include_resolved_questions: bool = False


class SharePayload(Schema):
    enabled: bool


@router.get("/{slug}/exports")
def list_exports(request, slug: str):
    project = get_project_or_404(slug)
    return {
        "items": [
            {
                "id": artifact.id,
                "format": artifact.format,
                "title": artifact.title,
                "filename": artifact.filename,
                "status": artifact.status,
                "share_enabled": artifact.share_enabled,
                "share_token": artifact.share_token,
            }
            for artifact in project.exports.all()
        ]
    }


@router.post("/{slug}/exports", auth=django_auth)
def create_export_endpoint(request, slug: str, payload: ExportPayload):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    artifact = create_export(project, payload.format, actor, payload.dict())
    return {"id": artifact.id, "filename": artifact.filename, "status": artifact.status}


@router.post("/{slug}/exports/{export_id}/share-toggle", auth=django_auth)
def toggle_share_endpoint(request, slug: str, export_id: int, payload: SharePayload):
    project = get_project_or_404(slug)
    artifact = project.exports.get(pk=export_id)
    toggle_share(artifact, payload.enabled)
    return {"ok": True, "share_enabled": artifact.share_enabled}
