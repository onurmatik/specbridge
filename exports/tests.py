import io
import json

from django.test import Client, TestCase
from django.urls import reverse
from docx import Document
from pypdf import PdfReader

from exports.models import ExportArtifact, ExportFormat
from exports.services import build_export_content
from projects.demo import ensure_demo_workspace
from specs.services import section_summaries


class ExportApiTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def _section_ids(self):
        return ",".join(section["id"] for section in section_summaries(self.project)[:2])

    def test_export_creation_endpoint_returns_download_url_for_all_file_types(self):
        for file_type in ("md", "pdf", "docx"):
            response = self.client.post(
                f"/api/projects/{self.project.slug}/exports",
                data=json.dumps(
                    {
                        "format": "agent",
                        "file_type": file_type,
                        "share_enabled": True,
                        "section_ids": self._section_ids(),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["download_url"].endswith(f"/projects/{self.project.slug}/exports/{payload['id']}/download/"))
            self.assertEqual(payload["file_type"], file_type)
            self.assertTrue(payload["filename"].endswith(f".{file_type}"))

        self.assertEqual(ExportArtifact.objects.filter(project=self.project, format="agent").count(), 3)

    def test_export_creation_endpoint_accepts_extension_alias(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/exports",
            data=json.dumps(
                {
                    "format": "tasks",
                    "extension": "docx",
                    "section_ids": self._section_ids(),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        artifact = ExportArtifact.objects.get(pk=payload["id"])
        self.assertEqual(artifact.configuration["file_type"], "docx")
        self.assertTrue(artifact.filename.endswith(".docx"))

    def test_list_exports_includes_download_url(self):
        artifact = ExportArtifact.objects.create(
            project=self.project,
            format=ExportFormat.PRD,
            title="Seed export",
            filename="seed.md",
            generated_by=self.project.created_by,
            configuration={"file_type": "md"},
            content="# Seed",
        )

        response = self.client.get(f"/api/projects/{self.project.slug}/exports")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        listed_artifact = next(item for item in payload["items"] if item["id"] == artifact.id)
        self.assertEqual(listed_artifact["download_url"], reverse("project-export-download", args=[self.project.slug, artifact.id]))
        self.assertEqual(listed_artifact["file_type"], "md")

    def test_download_endpoint_returns_markdown_content(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/exports",
            data=json.dumps({"format": "prd", "file_type": "md", "section_ids": self._section_ids()}),
            content_type="application/json",
        )
        artifact_id = response.json()["id"]

        download = self.client.get(reverse("project-export-download", args=[self.project.slug, artifact_id]))

        self.assertEqual(download.status_code, 200)
        self.assertIn("text/markdown", download["Content-Type"])
        self.assertIn(b"# ", download.content)
        self.assertIn(b"attachment;", download["Content-Disposition"].encode("utf-8"))

    def test_download_endpoint_returns_docx_bytes(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/exports",
            data=json.dumps({"format": "prd", "file_type": "docx", "section_ids": self._section_ids()}),
            content_type="application/json",
        )
        artifact_id = response.json()["id"]

        download = self.client.get(reverse("project-export-download", args=[self.project.slug, artifact_id]))

        self.assertEqual(download.status_code, 200)
        self.assertEqual(
            download["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        document = Document(io.BytesIO(download.content))
        self.assertIn(self.project.name, "\n".join(paragraph.text for paragraph in document.paragraphs))

    def test_download_endpoint_returns_pdf_bytes(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/exports",
            data=json.dumps({"format": "prd", "file_type": "pdf", "section_ids": self._section_ids()}),
            content_type="application/json",
        )
        artifact_id = response.json()["id"]

        download = self.client.get(reverse("project-export-download", args=[self.project.slug, artifact_id]))

        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")
        reader = PdfReader(io.BytesIO(download.content))
        self.assertIn(self.project.name, "\n".join(page.extract_text() or "" for page in reader.pages))

    def test_download_endpoint_requires_authentication(self):
        artifact = ExportArtifact.objects.create(
            project=self.project,
            format=ExportFormat.PRD,
            title="Seed export",
            filename="seed.md",
            generated_by=self.project.created_by,
            configuration={"file_type": "md"},
            content="# Seed",
        )

        anonymous_client = Client()
        response = anonymous_client.get(reverse("project-export-download", args=[self.project.slug, artifact.id]))

        self.assertEqual(response.status_code, 302)


class ExportContentTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()

    def test_agent_export_includes_coding_agent_prefix(self):
        content = build_export_content(self.project, ExportFormat.AGENT)

        self.assertTrue(content.startswith("You are implementing a single spec document workspace in SpecBridge."))

    def test_uiux_agent_export_includes_uiux_prompt_prefix(self):
        content = build_export_content(self.project, ExportFormat.UI_UX_AGENT)

        self.assertTrue(
            content.startswith(
                "Based on the spec below, write a prompt to the UI/UX agent to design the defined app and workflows."
            )
        )
        self.assertIn("key screens and navigation structure", content)

    def test_prd_tech_spec_and_tasks_exports_keep_same_body(self):
        prd = build_export_content(self.project, ExportFormat.PRD)
        tech_spec = build_export_content(self.project, ExportFormat.TECH_SPEC)
        tasks = build_export_content(self.project, ExportFormat.TASKS)

        self.assertEqual(prd, tech_spec)
        self.assertEqual(prd, tasks)
