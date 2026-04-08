from __future__ import annotations

from copy import deepcopy
from typing import Any

from specs.models import (
    AuditEvent,
    AuditEventType,
    ProjectRevision,
    ProjectSpecDocument,
    SpecDocumentRevision,
)
from specs.spec_document import (
    SPEC_SCHEMA_VERSION,
    build_primary_ref,
    delete_section,
    default_spec_content,
    find_section,
    find_section_by_identifier,
    insert_section_after,
    markdown_to_blocks,
    move_section,
    normalized_spec_content,
    section_catalog,
    section_markdown_from_ref,
    section_status_from_ref,
    section_summary,
    strip_redundant_section_heading,
    update_section_content,
)


def ensure_spec_document(project) -> ProjectSpecDocument:
    spec_document = getattr(project, "spec_document", None)
    if spec_document:
        update_fields: list[str] = []
        if not spec_document.content_json:
            spec_document.content_json = default_spec_content(project)
            update_fields.append("content_json")
        if spec_document.schema_version != SPEC_SCHEMA_VERSION:
            spec_document.schema_version = SPEC_SCHEMA_VERSION
            update_fields.append("schema_version")
        if update_fields:
            spec_document.save(update_fields=[*update_fields, "updated_at"])
        return spec_document

    return ProjectSpecDocument.objects.create(
        project=project,
        title=f"{project.name} Spec",
        schema_version=SPEC_SCHEMA_VERSION,
        content_json=default_spec_content(project),
    )


def bootstrap_spec_document(project) -> ProjectSpecDocument:
    spec_document = ensure_spec_document(project)
    if spec_document.content_json:
        return spec_document
    spec_document.content_json = default_spec_content(project)
    spec_document.schema_version = SPEC_SCHEMA_VERSION
    spec_document.save(update_fields=["content_json", "schema_version", "updated_at"])
    return spec_document


def section_summaries(project) -> list[dict[str, Any]]:
    return section_catalog(ensure_spec_document(project).content_json)


def build_primary_ref_for_section(project, section_id: str, *, excerpt: str = "") -> dict[str, Any]:
    section = find_section(ensure_spec_document(project).content_json, section_id)
    if not section:
        return {}
    return build_primary_ref(section, excerpt=excerpt)


def build_primary_ref_for_identifier(project, identifier: str, *, excerpt: str = "") -> dict[str, Any]:
    section = find_section_by_identifier(ensure_spec_document(project).content_json, identifier)
    if not section:
        return {}
    return build_primary_ref(section, excerpt=excerpt)


def build_spec_snapshot(project) -> dict[str, Any]:
    spec_document = ensure_spec_document(project)
    return {
        "id": spec_document.id,
        "title": spec_document.title,
        "schema_version": spec_document.schema_version,
        "content_json": deepcopy(normalized_spec_content(spec_document.content_json)),
        "sections": section_summaries(project),
    }


def build_project_snapshot(project) -> dict[str, Any]:
    return {
        "project": {
            "id": project.id,
            "slug": project.slug,
            "name": project.name,
            "tagline": project.tagline,
            "summary": project.summary,
        },
        "spec": build_spec_snapshot(project),
        "decisions": [
            {
                "id": decision.id,
                "code": decision.code,
                "title": decision.title,
                "summary": decision.summary,
                "status": decision.status,
                "primary_ref": decision.primary_ref,
                "implementation_progress": decision.implementation_progress,
            }
            for decision in project.decisions.all()
        ],
        "assumptions": [
            {
                "id": assumption.id,
                "title": assumption.title,
                "description": assumption.description,
                "status": assumption.status,
                "primary_ref": assumption.primary_ref,
                "impact": assumption.impact,
            }
            for assumption in project.assumptions.all()
        ],
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
    project_revision=None,
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
        project_revision=project_revision,
    )


def capture_spec_revision(
    *,
    spec_document: ProjectSpecDocument,
    title: str,
    summary: str = "",
    actor=None,
    project_revision: ProjectRevision | None = None,
):
    previous_revision = spec_document.revisions.order_by("-number").first()
    return SpecDocumentRevision.objects.create(
        spec_document=spec_document,
        number=(previous_revision.number + 1) if previous_revision else 1,
        title=title,
        summary=summary,
        snapshot=deepcopy(normalized_spec_content(spec_document.content_json)),
        created_by=actor,
        project_revision=project_revision,
        previous_revision=previous_revision,
    )


def capture_project_revision(
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
    previous_revision = project.revisions.order_by("-number").first()
    revision = ProjectRevision.objects.create(
        project=project,
        number=(previous_revision.number + 1) if previous_revision else 1,
        title=title,
        summary=summary,
        snapshot=build_project_snapshot(project),
        created_by=actor,
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        previous_revision=previous_revision,
    )
    capture_spec_revision(
        spec_document=ensure_spec_document(project),
        title=title,
        summary=summary,
        actor=actor,
        project_revision=revision,
    )
    log_audit_event(
        project=project,
        event_type=AuditEventType.PROJECT_REVISION_CREATED,
        title=f"Captured {project.name} r{revision.number}",
        description=summary or title,
        actor=actor,
        source_post=source_post,
        source_decision=source_decision,
        source_assumption=source_assumption,
        source_agent=source_agent,
        project_revision=revision,
        metadata={"revision": revision.number, "title": title},
    )
    return revision


def update_spec_section(
    *,
    project,
    section_id: str,
    actor=None,
    title: str | None = None,
    status: str | None = None,
    content_json: list[dict[str, Any]] | None = None,
):
    spec_document = ensure_spec_document(project)
    next_content, updated_section, changed = update_section_content(
        spec_document.content_json,
        section_id,
        title=title,
        status=status,
        content_blocks=content_json,
    )
    if not updated_section:
        raise ValueError("Section not found.")
    if not changed:
        return None

    spec_document.content_json = next_content
    spec_document.schema_version = SPEC_SCHEMA_VERSION
    spec_document.save(update_fields=["content_json", "schema_version", "updated_at"])
    summary_section = section_summary(updated_section)
    description = f"Updated section {summary_section['title']}"
    project_revision = capture_project_revision(
        project=project,
        title=description,
        summary=description,
        actor=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_UPDATED,
        title=description,
        description=description,
        metadata={"section_id": summary_section["id"], "status": summary_section["status"]},
        project_revision=project_revision,
    )
    from specs.concerns import mark_linked_concerns_stale

    mark_linked_concerns_stale(project=project, section_ids=[summary_section["id"]], actor=actor)
    return project_revision


def apply_batch_spec_operations(
    *,
    project,
    operations: list[dict[str, Any]],
    actor=None,
    title: str,
    summary: str = "",
    source_post=None,
):
    spec_document = ensure_spec_document(project)
    next_content = deepcopy(normalized_spec_content(spec_document.content_json))
    applied_operations: list[dict[str, Any]] = []
    touched_section_ids: list[str] = []

    for operation in operations:
        operation_type = (operation.get("type") or "").strip()
        if operation_type == "update_section":
            section_id = operation.get("section_id", "")
            existing_section = find_section(next_content, section_id)
            if not existing_section:
                continue
            normalized_body = strip_redundant_section_heading(
                operation.get("body", ""),
                section_summary(existing_section)["title"],
            )
            if not normalized_body:
                continue
            next_content, updated_section, changed = update_section_content(
                next_content,
                section_id,
                content_blocks=markdown_to_blocks(normalized_body),
            )
            if not updated_section or not changed:
                continue
            updated_summary = section_summary(updated_section)
            applied_operations.append(
                {
                    "type": operation_type,
                    "section_id": updated_summary["id"],
                    "section_title": updated_summary["title"],
                }
            )
            touched_section_ids.append(updated_summary["id"])
            continue

        if operation_type == "insert_section_after":
            after_section_id = operation.get("after_section_id", "")
            normalized_title = (operation.get("title") or "New Section").strip() or "New Section"
            normalized_body = strip_redundant_section_heading(operation.get("body", ""), normalized_title)
            if not normalized_body:
                continue
            next_content, inserted_section = insert_section_after(
                next_content,
                project=project,
                after_section_id=after_section_id,
                title=normalized_title,
                body=normalized_body,
            )
            if not inserted_section:
                continue
            inserted_summary = section_summary(inserted_section)
            applied_operations.append(
                {
                    "type": operation_type,
                    "section_id": inserted_summary["id"],
                    "section_title": inserted_summary["title"],
                    "after_section_id": after_section_id,
                }
            )
            touched_section_ids.append(inserted_summary["id"])

    if not applied_operations:
        return {"project_revision": None, "applied_operations": []}

    spec_document.content_json = next_content
    spec_document.schema_version = SPEC_SCHEMA_VERSION
    spec_document.save(update_fields=["content_json", "schema_version", "updated_at"])
    project_revision = capture_project_revision(
        project=project,
        title=title,
        summary=summary or title,
        actor=actor,
        source_post=source_post,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_UPDATED,
        title=title,
        description=summary or title,
        source_post=source_post,
        project_revision=project_revision,
        metadata={
            "operation_count": len(applied_operations),
            "section_ids": touched_section_ids,
        },
    )
    from specs.concerns import mark_linked_concerns_stale

    mark_linked_concerns_stale(project=project, section_ids=touched_section_ids, actor=actor)
    return {"project_revision": project_revision, "applied_operations": applied_operations}


def add_spec_section_after(
    *,
    project,
    after_section_id: str,
    actor=None,
    title: str = "New Section",
):
    spec_document = ensure_spec_document(project)
    next_content, inserted_section = insert_section_after(
        spec_document.content_json,
        project=project,
        after_section_id=after_section_id,
        title=title,
    )
    if not inserted_section:
        raise ValueError("Section not found.")

    spec_document.content_json = next_content
    spec_document.schema_version = SPEC_SCHEMA_VERSION
    spec_document.save(update_fields=["content_json", "schema_version", "updated_at"])

    summary_section = section_summary(inserted_section)
    description = f"Added section {summary_section['title']}"
    project_revision = capture_project_revision(
        project=project,
        title=description,
        summary=description,
        actor=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_CREATED,
        title=description,
        description=description,
        metadata={"section_id": summary_section["id"], "status": summary_section["status"]},
        project_revision=project_revision,
    )
    return summary_section


def reorder_spec_section(
    *,
    project,
    section_id: str,
    direction: str,
    actor=None,
):
    normalized_direction = (direction or "").strip().lower()
    if normalized_direction not in {"up", "down"}:
        raise ValueError("Section move direction must be 'up' or 'down'.")

    spec_document = ensure_spec_document(project)
    next_content, moved_section, changed = move_section(
        spec_document.content_json,
        section_id,
        direction=normalized_direction,
    )
    if not moved_section:
        raise ValueError("Section not found.")
    if not changed:
        raise ValueError("Section cannot be moved further.")

    spec_document.content_json = next_content
    spec_document.schema_version = SPEC_SCHEMA_VERSION
    spec_document.save(update_fields=["content_json", "schema_version", "updated_at"])

    summary_section = section_summary(moved_section)
    description = f"Moved section {summary_section['title']} {normalized_direction}"
    project_revision = capture_project_revision(
        project=project,
        title=description,
        summary=description,
        actor=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_REORDERED,
        title=description,
        description=description,
        metadata={"section_id": summary_section["id"], "direction": normalized_direction},
        project_revision=project_revision,
    )
    return summary_section


def delete_spec_section(
    *,
    project,
    section_id: str,
    actor=None,
):
    spec_document = ensure_spec_document(project)
    next_content, deleted_section, changed, focus_section_id = delete_section(spec_document.content_json, section_id)
    if not deleted_section:
        raise ValueError("Section not found.")
    if not changed:
        raise ValueError("Section could not be deleted.")

    spec_document.content_json = next_content
    spec_document.schema_version = SPEC_SCHEMA_VERSION
    spec_document.save(update_fields=["content_json", "schema_version", "updated_at"])

    summary_section = section_summary(deleted_section)
    description = f"Deleted section {summary_section['title']}"
    project_revision = capture_project_revision(
        project=project,
        title=description,
        summary=description,
        actor=actor,
    )
    log_audit_event(
        project=project,
        actor=actor,
        event_type=AuditEventType.DOCUMENT_DELETED,
        title=description,
        description=description,
        metadata={"section_id": summary_section["id"]},
        project_revision=project_revision,
    )

    from specs.concerns import mark_linked_concerns_stale

    mark_linked_concerns_stale(
        project=project,
        section_ids=[summary_section["id"]],
        actor=actor,
        trigger="spec_section_delete",
    )
    return {
        "deleted_section": summary_section,
        "focus_section_id": focus_section_id,
    }


def compare_section_revisions(left: SpecDocumentRevision, right: SpecDocumentRevision, section_id: str) -> dict[str, Any]:
    left_section = section_summary(find_section(left.snapshot, section_id) or {})
    right_section = section_summary(find_section(right.snapshot, section_id) or {})
    return {
        "title_changed": left_section.get("title") != right_section.get("title"),
        "body_changed": left_section.get("body") != right_section.get("body"),
        "status_changed": left_section.get("status") != right_section.get("status"),
        "previous": left_section,
        "current": right_section,
    }


def section_markdown_for_ref(project, primary_ref: dict | None) -> str:
    return section_markdown_from_ref(ensure_spec_document(project).content_json, primary_ref)


def section_title_for_ref(project, primary_ref: dict | None) -> str:
    if not isinstance(primary_ref, dict):
        return ""
    section = find_section(ensure_spec_document(project).content_json, primary_ref.get("section_id", ""))
    return section_summary(section).get("title", "") if section else primary_ref.get("label", "")


def section_status_for_ref(project, primary_ref: dict | None) -> str:
    return section_status_from_ref(ensure_spec_document(project).content_json, primary_ref)
