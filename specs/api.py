from ninja import Router, Schema
from ninja.security import django_auth

from projects.services import get_project_or_404, resolve_actor
from specs.models import Assumption, AssumptionStatus
from specs.services import apply_snapshot, capture_version, compare_versions, update_section

router = Router(tags=["specs"])


class SectionUpdatePayload(Schema):
    summary: str | None = None
    body: str | None = None
    status: str | None = None


class AssumptionPayload(Schema):
    title: str
    description: str
    section_key: str | None = None
    impact: str = "medium"


@router.get("/{slug}/sections")
def list_sections(request, slug: str):
    project = get_project_or_404(slug)
    return {
        "items": [
            {
                "id": section.id,
                "key": section.key,
                "title": section.title,
                "summary": section.summary,
                "body": section.body,
                "status": section.status,
                "order": section.order,
            }
            for section in project.sections.all()
        ]
    }


@router.get("/{slug}/sections/{key}")
def get_section(request, slug: str, key: str):
    project = get_project_or_404(slug)
    section = project.sections.get(key=key)
    return {
        "id": section.id,
        "key": section.key,
        "title": section.title,
        "summary": section.summary,
        "body": section.body,
        "status": section.status,
    }


@router.patch("/{slug}/sections/{key}", auth=django_auth)
def patch_section(request, slug: str, key: str, payload: SectionUpdatePayload):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    section = project.sections.get(key=key)
    update_section(
        section=section,
        actor=actor,
        summary=payload.summary,
        body=payload.body,
        status=payload.status,
    )
    return {"ok": True, "section": section.key, "status": section.status}


@router.post("/{slug}/assumptions", auth=django_auth)
def create_assumption(request, slug: str, payload: AssumptionPayload):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    section = project.sections.filter(key=payload.section_key).first() if payload.section_key else None
    assumption = Assumption.objects.create(
        project=project,
        section=section,
        title=payload.title,
        description=payload.description,
        impact=payload.impact,
        created_by=actor,
    )
    capture_version(
        project=project,
        title=f"Assumption added: {assumption.title}",
        summary=assumption.description,
        actor=actor,
        source_assumption=assumption,
    )
    return {"id": assumption.id, "status": assumption.status}


@router.post("/{slug}/assumptions/{assumption_id}/validate", auth=django_auth)
def validate_assumption(request, slug: str, assumption_id: int):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    assumption = project.assumptions.get(pk=assumption_id)
    assumption.status = AssumptionStatus.VALIDATED
    assumption.validated_by = actor
    assumption.save(update_fields=["status", "validated_by", "updated_at"])
    capture_version(
        project=project,
        title=f"Assumption validated: {assumption.title}",
        summary=assumption.description,
        actor=actor,
        source_assumption=assumption,
    )
    return {"ok": True, "status": assumption.status}


@router.post("/{slug}/assumptions/{assumption_id}/invalidate", auth=django_auth)
def invalidate_assumption(request, slug: str, assumption_id: int):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    assumption = project.assumptions.get(pk=assumption_id)
    assumption.status = AssumptionStatus.INVALIDATED
    assumption.validated_by = actor
    assumption.save(update_fields=["status", "validated_by", "updated_at"])
    capture_version(
        project=project,
        title=f"Assumption invalidated: {assumption.title}",
        summary=assumption.description,
        actor=actor,
        source_assumption=assumption,
    )
    return {"ok": True, "status": assumption.status}


@router.get("/{slug}/versions")
def list_versions(request, slug: str):
    project = get_project_or_404(slug)
    return {
        "items": [
            {
                "id": version.id,
                "number": version.number,
                "title": version.title,
                "summary": version.summary,
                "created_at": version.created_at.isoformat(),
            }
            for version in project.versions.order_by("-number")
        ]
    }


@router.get("/{slug}/versions/compare")
def compare_versions_endpoint(request, slug: str, left: int, right: int):
    project = get_project_or_404(slug)
    left_version = project.versions.get(number=left)
    right_version = project.versions.get(number=right)
    return {
        "left": left_version.number,
        "right": right_version.number,
        "rows": compare_versions(left_version, right_version),
    }


@router.post("/{slug}/versions/{version_id}/revert", auth=django_auth)
def revert_version(request, slug: str, version_id: int):
    project = get_project_or_404(slug)
    actor = resolve_actor(request, project)
    version = project.versions.get(pk=version_id)
    new_version = apply_snapshot(
        project=project,
        snapshot=version.snapshot,
        actor=actor,
        title=f"Reverted to v{version.number}",
    )
    return {"ok": True, "version": new_version.number}
