import hashlib
import json

from django.db import migrations


def _normalize_fingerprint(raw_value: str, fallback_seed: str) -> str:
    candidate = (raw_value or "").strip().lower()
    digest = hashlib.sha1((candidate or fallback_seed).encode("utf-8")).hexdigest()
    return digest[:32]


def migrate_existing_issues_to_concerns(apps, schema_editor):
    ConcernRun = apps.get_model("specs", "ConcernRun")
    ConcernStatus = apps.get_model("specs", "ProjectConcern")
    ConsistencyRun = apps.get_model("specs", "ConsistencyRun")
    ConsistencyIssue = apps.get_model("specs", "ConsistencyIssue")
    ProjectDocument = apps.get_model("specs", "ProjectDocument")
    OpenQuestion = apps.get_model("alignment", "OpenQuestion")
    Blocker = apps.get_model("alignment", "Blocker")

    run_map = {}
    for run in ConsistencyRun.objects.all():
        concern_run = ConcernRun.objects.create(
            project_id=run.project_id,
            provider=run.provider,
            model=run.model,
            status=run.status,
            concern_count=run.issue_count,
            error_message=run.error_message,
            scopes=["consistency"],
            trigger="migration",
            analyzed_at=run.analyzed_at,
        )
        run_map[run.id] = concern_run.id

    for issue in ConsistencyIssue.objects.all():
        fallback_seed = json.dumps(
            {"title": issue.title, "summary": issue.summary, "source_refs": issue.source_refs},
            sort_keys=True,
        )
        concern = ConcernStatus.objects.create(
            project_id=issue.project_id,
            run_id=run_map.get(issue.run_id),
            fingerprint=_normalize_fingerprint(issue.fingerprint, fallback_seed),
            concern_type="consistency",
            raised_by_kind="ai",
            title=issue.title,
            summary=issue.summary,
            severity=issue.severity,
            status=issue.status,
            recommendation=issue.recommendation,
            source_refs=issue.source_refs,
            detected_at=issue.detected_at,
            last_seen_at=issue.last_seen_at,
            resolved_at=issue.resolved_at,
            dismissed_at=issue.dismissed_at,
            last_reevaluated_at=issue.last_seen_at,
        )
        document_ids = [
            document.id
            for document in ProjectDocument.objects.filter(project_id=issue.project_id)
            if document.slug in {ref.get("identifier") for ref in issue.source_refs if ref.get("kind") == "document"}
        ]
        if document_ids:
            concern.documents.set(document_ids)

    for question in OpenQuestion.objects.all():
        concern = ConcernStatus.objects.create(
            project_id=question.project_id,
            source_post_id=question.source_post_id,
            fingerprint=_normalize_fingerprint(
                f"question-{question.id}",
                json.dumps({"title": question.title, "details": question.details}, sort_keys=True),
            ),
            concern_type="human_flag",
            raised_by_kind="human" if question.raised_by_id else "system",
            title=question.title,
            summary=question.details,
            severity=question.severity,
            status="resolved" if question.status == "resolved" else "open",
            recommendation="Discuss the concern and re-evaluate it once the affected documents are updated.",
            source_refs=[
                *(
                    [{"kind": "stream_post", "identifier": str(question.source_post_id), "label": f"Activity post #{question.source_post_id}"}]
                    if question.source_post_id
                    else []
                ),
                *(
                    [{"kind": "document", "identifier": question.related_document.slug, "label": question.related_document.title}]
                    if question.related_document_id
                    else []
                ),
            ],
            detected_at=question.created_at,
            last_seen_at=question.updated_at,
            resolved_at=question.resolved_at,
            created_by_id=question.raised_by_id,
            resolved_by_id=question.resolved_by_id,
        )
        if question.related_document_id:
            concern.documents.set([question.related_document_id])

    for blocker in Blocker.objects.all():
        concern = ConcernStatus.objects.create(
            project_id=blocker.project_id,
            source_post_id=blocker.source_post_id,
            fingerprint=_normalize_fingerprint(
                f"blocker-{blocker.id}",
                json.dumps({"title": blocker.title, "details": blocker.details}, sort_keys=True),
            ),
            concern_type="implementability",
            raised_by_kind="human" if blocker.raised_by_id else "system",
            title=blocker.title,
            summary=blocker.details,
            severity=blocker.severity,
            status="resolved" if blocker.status == "resolved" else "open",
            recommendation="Unblock the linked documents, then re-evaluate the concern.",
            source_refs=[
                *(
                    [{"kind": "stream_post", "identifier": str(blocker.source_post_id), "label": f"Activity post #{blocker.source_post_id}"}]
                    if blocker.source_post_id
                    else []
                ),
                *(
                    [{"kind": "document", "identifier": blocker.related_document.slug, "label": blocker.related_document.title}]
                    if blocker.related_document_id
                    else []
                ),
            ],
            detected_at=blocker.created_at,
            last_seen_at=blocker.updated_at,
            resolved_at=blocker.resolved_at,
            created_by_id=blocker.raised_by_id,
            resolved_by_id=blocker.resolved_by_id,
        )
        if blocker.related_document_id:
            concern.documents.set([blocker.related_document_id])


class Migration(migrations.Migration):

    dependencies = [
        ("specs", "0004_alter_auditevent_event_type_concernrun_and_more"),
        ("alignment", "0004_streampost_concern"),
    ]

    operations = [
        migrations.RunPython(migrate_existing_issues_to_concerns, migrations.RunPython.noop),
    ]
