from pathlib import Path

from projects.models import Project

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_ASSET_PATHS = (
    BASE_DIR / "static" / "dist" / "app.css",
    BASE_DIR / "static" / "js" / "app.js",
)


def active_project_context(request):
    project = None
    slug = None
    if request.resolver_match:
        slug = request.resolver_match.kwargs.get("slug")
    if slug:
        project = Project.objects.filter(slug=slug).first()
    return {"active_project": project}


def frontend_runtime_context(request):
    mtimes = []
    for asset_path in FRONTEND_ASSET_PATHS:
        try:
            mtimes.append(int(asset_path.stat().st_mtime))
        except FileNotFoundError:
            continue
    return {
        "frontend_asset_version": str(max(mtimes)) if mtimes else "dev",
        "frontend_disable_service_workers": True,
    }
