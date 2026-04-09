from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.utils.http import content_disposition_header

from exports.services import render_export_bytes
from projects.services import get_project_or_404


@login_required
def download_export(request, slug, export_id):
    project = get_project_or_404(slug, request.user)
    try:
        artifact = project.exports.get(pk=export_id)
    except project.exports.model.DoesNotExist as exc:
        raise Http404("Export not found") from exc

    payload, content_type = render_export_bytes(artifact)
    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(True, artifact.filename)
    response["Cache-Control"] = "no-store"
    return response
