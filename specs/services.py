from __future__ import annotations

from typing import Any

from specs.models import AuditEvent, AuditEventType, SpecSection, SpecVersion


def build_spec_snapshot(project) -> dict[str, Any]:
    sections = [
        {
            "key": section.key,
            "title": section.title,
            "summary": section.summary,
            "body": section.body,
            "status": section.status,
            "order": section.order,
            "assumptions": [
                {
                    "id": assumption.id,
                    "title": assumption.title,
                    "status": assumption.status,
                }
                for assumption in section.assumptions.all()
            ],
        }
        for section in project.sections.prefetch_related("assumptions").all()
    ]
    decisions = [
        {
            "id": decision.id,
            "code": decision.code,
            "title": decision.title,
            "summary": decision.summary,
            "status": decision.status,
            "related_section_key": decision.related_section_key,
            "implementation_progress": decision.implementation_progress,
        }
        for decision in project.decisions.all()
    ]
    assumptions = [
        {
            "id": assumption.id,
            "title": assumption.title,
            "description": assumption.description,
            "status": assumption.status,
            "section_key": assumption.section.key if assumption.section else "",
            "impact": assumption.impact,
        }
        for assumption in project.assumptions.select_related("section").all()
    ]
    return {
        "project": {
            "id": project.id,
            "slug": project.slug,
            "name": project.name,
            "tagline": project.tagline,
            "summary": project.summary,
        },
        "sections": sections,
        "decisions": decisions,
        "assumptions": assumptions,
    }


def log_audit_event(
    *,
    project,
    event_type: str,
    title: str,
    description: str = "",
    actor=None,
    metadata: dict[str, Any] | None = None,
    source_post=None,
    source_decision=None,
    source_assumption=None,
    source_agent=None,
    spec_version=None,
):
    return AuditEvent.objects.create(
        project=project,
        actor=actor,
        event_type=event_type,
        title=title,
        description=description,
        metadata=metadata or {},
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        spec_version=spec_version,
    )


def capture_version(
    *,
    project,
    title: str,
    summary: str = "",
    actor=None,
    source_post=None,
    source_decision=None,
    source_assumption=None,
    source_agent=None,
):
    previous_version = project.versions.order_by("-number").first()
    version = SpecVersion.objects.create(
        project=project,
        number=(previous_version.number + 1) if previous_version else 1,
        title=title,
        summary=summary,
        snapshot=build_spec_snapshot(project),
        created_by=actor,
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        previous_version=previous_version,
    )
    log_audit_event(
        project=project,
        event_type=AuditEventType.VERSION_CREATED,
        title=f"Captured {project.name} v{version.number}",
        description=summary or title,
        actor=actor,
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        spec_version=version,
        metadata={"version": version.number, "title": title},
    )
    return version


def update_section(
    *,
    section: SpecSection,
    actor=None,
    summary: str | None = None,
    body: str | None = None,
    status: str | None = None,
    linked_decision=None,
    linked_assumption=None,
):
    if summary is not None:
        section.summary = summary
    if body is not None:
        section.body = body
    if status is not None:
        section.status = status
    section.save()
    description = f"Updated section {section.title}"
    log_audit_event(
        project=section.project,
        actor=actor,
        event_type=AuditEventType.SECTION_UPDATED,
        title=description,
        description=description,
        source_decision=linked_decision,
        source_assumption=linked_assumption,
        metadata={"section_key": section.key, "status": section.status},
    )
    return capture_version(
        project=section.project,
        title=f"Section updated: {section.title}",
        summary=description,
        actor=actor,
        source_decision=linked_decision,
        source_assumption=linked_assumption,
    )


def compare_versions(left: SpecVersion, right: SpecVersion) -> list[dict[str, Any]]:
    left_sections = {section["key"]: section for section in left.snapshot.get("sections", [])}
    right_sections = {section["key"]: section for section in right.snapshot.get("sections", [])}
    rows = []
    for key in sorted(set(left_sections) | set(right_sections)):
        previous = left_sections.get(key)
        current = right_sections.get(key)
        if previous and not current:
            change = "removed"
        elif current and not previous:
            change = "added"
        elif previous != current:
            change = "modified"
        else:
            change = "unchanged"
        rows.append(
            {
                "key": key,
                "title": (current or previous)["title"],
                "change": change,
                "previous": previous,
                "current": current,
            }
        )
    return rows


def apply_snapshot(*, project, snapshot: dict[str, Any], actor=None, title="Reverted to version"):
    snapshot_sections = snapshot.get("sections", [])
    existing = {section.key: section for section in project.sections.all()}
    for payload in snapshot_sections:
        section = existing.get(payload["key"])
        if section:
            section.title = payload["title"]
            section.summary = payload.get("summary", "")
            section.body = payload.get("body", "")
            section.status = payload.get("status", section.status)
            section.order = payload.get("order", section.order)
            section.save()
        else:
            SpecSection.objects.create(
                project=project,
                key=payload["key"],
                title=payload["title"],
                summary=payload.get("summary", ""),
                body=payload.get("body", ""),
                status=payload.get("status", "iterating"),
                order=payload.get("order", 0),
            )
    return capture_version(project=project, title=title, summary=title, actor=actor)
