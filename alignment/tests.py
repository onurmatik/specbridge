import io
import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from docx import Document
from pypdf import PdfWriter

from alignment.models import (
    Decision,
    DecisionStatus,
    OpenQuestion,
    StreamAttachmentExtractionStatus,
    StreamPost,
    StreamPostKind,
    StreamPostProcessingStatus,
)
from alignment.stream_attachments import (
    StreamSpecApplyResult,
    attach_files_to_post,
    process_stream_post_upload,
    process_uploaded_documents_for_post,
)
from projects.demo import ensure_demo_workspace
from specs.models import ProjectConcern
from specs.services import ensure_spec_document, section_summaries
from specs.spec_document import find_section, section_catalog

User = get_user_model()


def build_text_pdf_bytes(text: str) -> bytes:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content_stream = f"BT\n/F1 12 Tf\n72 720 Td\n({escaped_text}) Tj\nET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content_stream), content_stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    header = b"%PDF-1.4\n"
    body_parts = []
    offsets = [0]
    current_offset = len(header)
    for index, obj in enumerate(objects, start=1):
        offsets.append(current_offset)
        object_bytes = f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
        body_parts.append(object_bytes)
        current_offset += len(object_bytes)
    xref_offset = current_offset

    xref_lines = [f"xref\n0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    xref_lines.extend(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:])
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii")
    )
    return header + b"".join(body_parts) + b"".join(xref_lines) + trailer


class AlignmentMediaTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_dir.cleanup)

    def make_text_file(self, name: str = "notes.txt", content: str = "Reference text") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/plain")

    def make_markdown_file(self, name: str = "notes.md", content: str = "# Heading\n\n- item") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/markdown")

    def make_docx_file(self, name: str = "spec.docx", paragraphs: tuple[str, ...] = ("DOCX body",)) -> SimpleUploadedFile:
        buffer = io.BytesIO()
        document = Document()
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
        document.save(buffer)
        return SimpleUploadedFile(
            name,
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def make_pdf_file(self, name: str = "spec.pdf", text: str = "PDF content") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, build_text_pdf_bytes(text), content_type="application/pdf")

    def make_blank_pdf_file(self, name: str = "blank.pdf") -> SimpleUploadedFile:
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = io.BytesIO()
        writer.write(buffer)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/pdf")


class AlignmentApiTests(AlignmentMediaTestCase):
    def setUp(self):
        super().setUp()
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def test_mark_decision_implemented_endpoint(self):
        decision = Decision.objects.get(title="Retain SSO, Migrate Passwords")
        response = self.client.post(
            f"/api/projects/{self.project.slug}/decisions/{decision.id}/mark-implemented",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        decision.refresh_from_db()
        self.assertEqual(decision.status, DecisionStatus.IMPLEMENTED)

    def test_resolve_question_endpoint(self):
        question = OpenQuestion.objects.get(title="Fallback for delayed emails?")
        response = self.client.post(
            f"/api/projects/{self.project.slug}/questions/{question.id}/resolve",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        question.refresh_from_db()
        self.assertEqual(question.status, "resolved")

    def test_create_stream_post_endpoint(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data=json.dumps({"body": "  Need a fast draft for infra ownership.  "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["body"], "Need a fast draft for infra ownership.")
        self.assertEqual(response.json()["attachments"], [])
        self.assertTrue(
            StreamPost.objects.filter(project=self.project, body="Need a fast draft for infra ownership.").exists()
        )

    def test_create_stream_post_can_target_selected_concern(self):
        concern = ProjectConcern.objects.filter(project=self.project).first()

        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data=json.dumps({"body": "  Posting into the concern thread.  ", "concern_id": concern.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        post = StreamPost.objects.get(body="Posting into the concern thread.")
        self.assertEqual(post.concern_id, concern.id)

    def test_create_stream_post_accepts_upload_only_multipart(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={"body": "", "files": self.make_text_file(name="existing-spec.txt", content="Imported spec")},
        )

        self.assertEqual(response.status_code, 200)
        post = StreamPost.objects.get(pk=response.json()["id"])
        self.assertEqual(post.body, "")
        self.assertEqual(post.attachments.count(), 1)
        attachment = post.attachments.get()
        self.assertEqual(attachment.original_name, "existing-spec.txt")
        self.assertEqual(response.json()["attachments"][0]["original_name"], "existing-spec.txt")

    def test_create_stream_post_with_body_and_files_returns_processing_handle(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={
                "body": "Populate the spec with this.",
                "files": self.make_text_file(name="integration.txt", content="Integration requirements"),
            },
        )

        self.assertEqual(response.status_code, 200)
        post = StreamPost.objects.get(pk=response.json()["id"])
        self.assertEqual(post.attachments.count(), 1)
        self.assertEqual(post.processing_status, StreamPostProcessingStatus.PENDING)
        self.assertTrue(response.json()["processing_pending"])
        self.assertIn(f"/api/projects/{self.project.slug}/stream/{post.id}/process-files", response.json()["processing_url"])

    @patch("alignment.api.process_stream_post_upload")
    def test_process_stream_post_files_endpoint_runs_background_processing(self, mock_process_stream_post_upload):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={
                "body": "Populate the spec with this.",
                "files": self.make_text_file(name="integration.txt", content="Integration requirements"),
            },
        )
        post = StreamPost.objects.get(pk=response.json()["id"])
        post.processing_status = StreamPostProcessingStatus.COMPLETED
        post.save(update_fields=["processing_status", "updated_at"])
        mock_process_stream_post_upload.return_value = StreamSpecApplyResult(
            summary="",
            applied_operations=[],
            project_revision=None,
            agent_post=None,
        )

        process_response = self.client.post(
            f"/api/projects/{self.project.slug}/stream/{post.id}/process-files",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(process_response.status_code, 200)
        mock_process_stream_post_upload.assert_called_once()

    def test_process_stream_post_files_failure_keeps_post_and_creates_agent_notice(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={
                "body": "Populate the spec with this.",
                "files": self.make_blank_pdf_file(name="broken.pdf"),
            },
        )
        post = StreamPost.objects.get(pk=response.json()["id"])

        process_response = self.client.post(
            f"/api/projects/{self.project.slug}/stream/{post.id}/process-files",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(process_response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.attachments.count(), 1)
        self.assertEqual(post.processing_status, StreamPostProcessingStatus.FAILED)
        self.assertTrue(
            StreamPost.objects.filter(project=self.project, kind=StreamPostKind.AGENT, concern=post.concern).exists()
        )

    def test_create_stream_post_rejects_unsupported_type(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={
                "body": "",
                "files": SimpleUploadedFile("notes.csv", b"a,b,c\n1,2,3\n", content_type="text/csv"),
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("unsupported type", response.json()["errors"]["files"][0])

    def test_create_stream_post_rejects_oversized_file(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={
                "body": "",
                "files": SimpleUploadedFile(
                    "large.txt",
                    b"x" * ((20 * 1024 * 1024) + 1),
                    content_type="text/plain",
                ),
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("20 MB limit", response.json()["errors"]["files"][0])

    def test_create_stream_post_requires_body_or_files(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data=json.dumps({"body": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["errors"]["body"], ["Message is required."])

    def test_create_stream_post_can_upload_file_into_selected_concern(self):
        concern = ProjectConcern.objects.filter(project=self.project).first()

        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data={
                "body": "",
                "concern_id": concern.id,
                "files": self.make_text_file(name="concern-notes.txt", content="Concern notes"),
            },
        )

        self.assertEqual(response.status_code, 200)
        post = StreamPost.objects.get(pk=response.json()["id"])
        self.assertEqual(post.concern_id, concern.id)
        self.assertEqual(post.attachments.count(), 1)

    def test_promote_stream_post_to_concern_endpoint(self):
        post = StreamPost.objects.create(
            project=self.project,
            author=self.project.created_by,
            actor_name=self.project.created_by.display_name,
            actor_title=self.project.created_by.title,
            body="Infra and requirements still disagree about fallback ownership.",
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream/{post.id}/promote-to-concern",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertIsNotNone(post.concern_id)
        self.assertTrue(ProjectConcern.objects.filter(pk=post.concern_id, project=self.project).exists())

    def test_download_stream_attachment_requires_membership(self):
        member_post = StreamPost.objects.create(
            project=self.project,
            author=self.project.created_by,
            actor_name=self.project.created_by.display_name,
            actor_title=self.project.created_by.title,
            body="Shared file",
        )
        attachment = attach_files_to_post(member_post, [self.make_text_file(name="member.txt", content="Member doc")])[0]

        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="SpecBridge!123",
        )
        outsider_client = Client()
        outsider_client.force_login(outsider)

        response = outsider_client.get(f"/api/projects/{self.project.slug}/files/{attachment.id}/download")

        self.assertEqual(response.status_code, 404)

    def test_download_stream_attachment_returns_file_for_member(self):
        post = StreamPost.objects.create(
            project=self.project,
            author=self.project.created_by,
            actor_name=self.project.created_by.display_name,
            actor_title=self.project.created_by.title,
            body="Shared file",
        )
        attachment = attach_files_to_post(post, [self.make_text_file(name="member.txt", content="Member doc")])[0]

        response = self.client.get(f"/api/projects/{self.project.slug}/files/{attachment.id}/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Content-Type"), "text/plain")
        self.assertEqual(b"".join(response.streaming_content), b"Member doc")


class StreamAttachmentParsingTests(AlignmentMediaTestCase):
    def setUp(self):
        super().setUp()
        self.project = ensure_demo_workspace()
        self.post = StreamPost.objects.create(
            project=self.project,
            author=self.project.created_by,
            actor_name=self.project.created_by.display_name,
            actor_title=self.project.created_by.title,
            body="File upload",
        )

    def test_attach_files_to_post_extracts_supported_text_formats(self):
        attachments = attach_files_to_post(
            self.post,
            [
                self.make_text_file(name="plain.txt", content="Plain text reference"),
                self.make_markdown_file(name="notes.md", content="# Markdown\n\n- One"),
                self.make_docx_file(name="doc.docx", paragraphs=("DOCX paragraph",)),
                self.make_pdf_file(name="doc.pdf", text="PDF reference text"),
            ],
        )

        self.assertEqual(len(attachments), 4)
        self.assertTrue(
            all(attachment.extraction_status == StreamAttachmentExtractionStatus.COMPLETED for attachment in attachments)
        )
        extracted = {attachment.original_name: attachment.extracted_text for attachment in attachments}
        self.assertIn("Plain text reference", extracted["plain.txt"])
        self.assertIn("Markdown", extracted["notes.md"])
        self.assertIn("DOCX paragraph", extracted["doc.docx"])
        self.assertIn("PDF reference text", extracted["doc.pdf"])

    def test_attach_files_to_post_marks_blank_pdf_as_failed(self):
        attachment = attach_files_to_post(self.post, [self.make_blank_pdf_file()])[0]

        self.assertEqual(attachment.extraction_status, StreamAttachmentExtractionStatus.FAILED)
        self.assertIn("No extractable text", attachment.extraction_error)


class StreamAttachmentApplyTests(AlignmentMediaTestCase):
    def setUp(self):
        super().setUp()
        self.project = ensure_demo_workspace()
        self.post = StreamPost.objects.create(
            project=self.project,
            author=self.project.created_by,
            actor_name=self.project.created_by.display_name,
            actor_title=self.project.created_by.title,
            body="Populate the spec with this.",
        )
        attach_files_to_post(
            self.post,
            [self.make_text_file(name="integration.txt", content="Add a third-party integration section.")],
        )

    @patch("alignment.stream_attachments._request_openai")
    def test_process_uploaded_documents_updates_spec_and_creates_agent_notice(self, mock_request_openai):
        self.project.spec_language = "tr"
        self.project.save(update_fields=["spec_language", "updated_at"])
        sections = section_summaries(self.project)
        requirements = next(section for section in sections if section["title"] == "Requirements")
        tech_stack = next(section for section in sections if section["title"] == "Tech Stack")
        mock_request_openai.return_value = (
            "gpt-5-mini",
            {
                "summary": "Applied uploaded integration guidance.",
                "operations": [
                    {
                        "type": "update_section",
                        "section_id": requirements["id"],
                        "body": "## Requirements\n\nUpdated requirements body from uploaded reference.",
                    },
                    {
                        "type": "insert_section_after",
                        "after_section_id": tech_stack["id"],
                        "title": "Integration",
                        "body": "# Integration\n\nIntegration section body from uploaded reference.",
                    },
                ],
            },
        )

        result = process_uploaded_documents_for_post(
            self.post,
            prompt=self.post.body,
            actor=self.project.created_by,
        )

        spec_document = ensure_spec_document(self.project)
        updated_requirements = find_section(spec_document.content_json, requirements["id"])
        sections_after = section_catalog(spec_document.content_json)
        inserted_section = next(section for section in sections_after if section["title"] == "Integration")
        inserted_section_node = find_section(spec_document.content_json, inserted_section["id"])
        latest_revision = self.project.revisions.order_by("-number").first()

        self.assertEqual(
            updated_requirements["content"][0]["content"][0]["text"],
            "Updated requirements body from uploaded reference.",
        )
        self.assertEqual(inserted_section["body"], "Integration section body from uploaded reference.")
        self.assertEqual(
            inserted_section_node["content"][0]["content"][0]["text"],
            "Integration section body from uploaded reference.",
        )
        self.assertEqual(latest_revision.source_post_id, self.post.id)
        self.assertEqual(result.agent_post.kind, StreamPostKind.AGENT)
        self.assertIn("Updated Requirements", result.agent_post.body)
        self.assertIn("Added Integration", result.agent_post.body)
        self.assertIn("Return spec-ready Turkish content only.", mock_request_openai.call_args.kwargs["prompt"])
