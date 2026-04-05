from django.db import migrations


DOCUMENT_PRESETS = (
    ("overview", "Overview", "overview"),
)


def seed_default_documents(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    ProjectDocument = apps.get_model("specs", "ProjectDocument")
    ProjectRevision = apps.get_model("specs", "ProjectRevision")
    Assumption = apps.get_model("specs", "Assumption")
    Decision = apps.get_model("alignment", "Decision")

    for project in Project.objects.all():
        existing_documents = list(ProjectDocument.objects.filter(project=project).order_by("order", "created_at"))
        if not existing_documents:
            for index, (slug, title, document_type) in enumerate(DOCUMENT_PRESETS, start=1):
                ProjectDocument.objects.create(
                    project=project,
                    slug=slug,
                    title=title,
                    document_type=document_type,
                    source_kind="preset",
                    body="",
                    status="iterating",
                    order=index,
                    is_required=False,
                )
            existing_documents = list(ProjectDocument.objects.filter(project=project).order_by("order", "created_at"))

        if ProjectRevision.objects.filter(project=project).exists():
            continue

        snapshot = {
            "project": {
                "id": project.id,
                "slug": project.slug,
                "name": project.name,
                "tagline": project.tagline,
                "summary": project.summary,
            },
            "documents": [
                {
                    "slug": document.slug,
                    "title": document.title,
                    "document_type": document.document_type,
                    "source_kind": document.source_kind,
                    "body": document.body,
                    "status": document.status,
                    "order": document.order,
                    "is_required": document.is_required,
                }
                for document in existing_documents
            ],
            "decisions": [
                {
                    "id": decision.id,
                    "code": decision.code,
                    "title": decision.title,
                    "summary": decision.summary,
                    "status": decision.status,
                    "related_document_slug": "",
                    "related_document_title": "",
                    "implementation_progress": decision.implementation_progress,
                }
                for decision in Decision.objects.filter(project=project)
            ],
            "assumptions": [
                {
                    "id": assumption.id,
                    "title": assumption.title,
                    "description": assumption.description,
                    "status": assumption.status,
                    "document_slug": "",
                    "document_title": "",
                    "impact": assumption.impact,
                }
                for assumption in Assumption.objects.filter(project=project)
            ],
        }
        ProjectRevision.objects.create(
            project=project,
            number=1,
            title="Migrated to multi-document workspace",
            summary="Seeded the initial overview document during the multi-document migration.",
            snapshot=snapshot,
            created_by=project.created_by,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("alignment", "0002_remove_blocker_related_section_key_and_more"),
        ("specs", "0002_remove_assumption_section_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_default_documents, migrations.RunPython.noop),
    ]
