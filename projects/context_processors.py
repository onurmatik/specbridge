from projects.models import Project


def active_project_context(request):
    project = None
    slug = None
    if request.resolver_match:
        slug = request.resolver_match.kwargs.get("slug")
    if slug:
        project = Project.objects.filter(slug=slug).first()
    return {"active_project": project}
