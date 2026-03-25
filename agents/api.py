from ninja import Router
from ninja.security import django_auth

from agents.services import apply_suggestion, dismiss_suggestion
from projects.services import get_project_or_404, resolve_actor

router = Router(tags=["agents"])


@router.get("/{slug}/agent-suggestions")
def list_suggestions(request, slug: str):
    project = get_project_or_404(slug)
    return {
        "items": [
            {
                "id": suggestion.id,
                "title": suggestion.title,
                "summary": suggestion.summary,
                "status": suggestion.status,
                "related_section_key": suggestion.related_section_key,
            }
            for suggestion in project.agent_suggestions.all()
        ]
    }


@router.post("/{slug}/agent-suggestions/{suggestion_id}/apply", auth=django_auth)
def apply_suggestion_endpoint(request, slug: str, suggestion_id: int):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    suggestion = project.agent_suggestions.get(pk=suggestion_id)
    apply_suggestion(suggestion, actor)
    return {"ok": True, "status": suggestion.status}


@router.post("/{slug}/agent-suggestions/{suggestion_id}/dismiss", auth=django_auth)
def dismiss_suggestion_endpoint(request, slug: str, suggestion_id: int):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    suggestion = project.agent_suggestions.get(pk=suggestion_id)
    dismiss_suggestion(suggestion, actor)
    return {"ok": True, "status": suggestion.status}
