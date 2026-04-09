import json
import re
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from alignment.models import StreamPost, StreamPostProcessingStatus
from alignment.stream_attachments import attach_files_to_post
from projects.demo import ensure_demo_workspace
from projects.invitations import get_invite_for_token, invitation_token
from projects.models import MembershipRole, Project, ProjectInvite, ProjectMembership
from projects.services import create_project_workspace, section_summaries
from specs.services import update_spec_section
from specs.spec_document import markdown_to_blocks

User = get_user_model()


class ProjectPageTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_dir.cleanup)
        self.project = ensure_demo_workspace()
        self.client = Client()

    def _create_attachment_post(self, *, body: str = "", filename: str = "reference.txt", content: str = "Ref text"):
        post = StreamPost.objects.create(
            project=self.project,
            author=self.project.created_by,
            actor_name=self.project.created_by.display_name,
            actor_title=self.project.created_by.title,
            body=body,
        )
        attach_files_to_post(
            post,
            [SimpleUploadedFile(filename, content.encode("utf-8"), content_type="text/plain")],
        )
        return post

    def test_project_directory_renders(self):
        response = self.client.get(reverse("project-directory"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agent-Driven Spec System")
        self.assertContains(response, self.project.name)
        self.assertContains(response, "Public demo workspace")
        self.assertContains(response, "Issue status")
        self.assertContains(response, "Fallback mismatch across requirements, UI/UX, and infra")
        self.assertNotContains(response, "Primary route")
        self.assertContains(response, "data-project-modal-trigger", html=False)
        self.assertContains(response, "dist/app.css?v=", html=False)
        self.assertContains(response, "js/app.js?v=", html=False)

    def test_service_worker_stub_renders(self):
        response = self.client.get("/service-worker.js")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertContains(response, "self.registration.unregister", html=False)

    def test_anonymous_directory_only_shows_demo_workspace(self):
        outsider = User.objects.create_user(
            username="ada",
            email="ada@example.com",
            password="SpecBridge!123",
            first_name="Ada",
            last_name="Lovelace",
        )
        private_project = create_project_workspace(
            actor=outsider,
            project_name="Roadmap Console",
            tagline="Private roadmap coordination workspace.",
        )

        response = self.client.get(reverse("project-directory"))

        self.assertContains(response, self.project.name)
        self.assertNotContains(response, private_project.name)

    def test_project_pages_render(self):
        paths = [
            reverse("project-workspace", args=[self.project.slug]),
            reverse("project-dashboard", args=[self.project.slug]),
            reverse("project-decisions", args=[self.project.slug]),
            reverse("project-history", args=[self.project.slug]),
            reverse("project-handoff", args=[self.project.slug]),
            reverse("project-assumptions", args=[self.project.slug]),
            reverse("project-members", args=[self.project.slug]),
        ]
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_handoff_page_renders_export_controls(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(reverse("project-handoff", args=[self.project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-format-button="uiux_agent"', html=False)
        self.assertContains(response, 'data-file-type-button="md"', html=False)
        self.assertContains(response, 'data-file-type-button="pdf"', html=False)
        self.assertContains(response, 'data-file-type-button="docx"', html=False)
        self.assertContains(response, 'data-file-type-input', html=False)
        self.assertContains(response, 'data-export-download-form="true"', html=False)
        self.assertContains(response, 'flex flex-nowrap gap-2', html=False)
        self.assertContains(response, 'class="app-shell h-screen"', html=False)
        self.assertContains(response, 'overflow-hidden bg-gray-50 text-gray-900', html=False)
        self.assertContains(response, 'flex min-h-0 flex-1 overflow-hidden', html=False)
        self.assertContains(response, 'min-h-0 w-72', html=False)
        self.assertContains(response, 'min-h-0 w-96', html=False)
        html = response.content.decode("utf-8")
        self.assertLess(html.index("File Type"), html.index("Generate Export"))
        self.assertLess(html.index("Generate Export"), html.index("Access & Sharing"))

    def test_authenticated_workspace_renders_unified_spec_and_issues_rail(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(reverse("project-workspace", args=[self.project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-workspace-live-refresh-root', html=False)
        self.assertContains(response, 'data-workspace-header-region', html=False)
        self.assertContains(response, 'data-workspace-stream-live-region', html=False)
        self.assertContains(response, 'data-workspace-stream-scroll', html=False)
        self.assertContains(response, 'data-workspace-spec-region', html=False)
        self.assertContains(response, 'data-workspace-stream-composer', html=False)
        self.assertContains(response, 'data-api-method="PATCH"', html=False)
        self.assertContains(response, 'data-api-loading-label="Scanning..."', html=False)
        self.assertContains(response, 'data-api-loading-label="Posting..."', html=False)
        self.assertContains(response, 'data-api-loading-label="Running..."', html=False)
        self.assertContains(response, 'data-api-loading-label="Resolving..."', html=False)
        self.assertContains(response, 'data-api-submit-button', html=False)
        self.assertContains(response, 'data-api-button-icon', html=False)
        self.assertContains(response, 'data-spec-section-form', html=False)
        self.assertContains(response, 'data-spec-section-editor', html=False)
        self.assertContains(response, 'data-spec-section-markdown', html=False)
        self.assertContains(response, 'data-spec-nav-link', html=False)
        self.assertContains(response, 'data-spec-nav-fade-left', html=False)
        self.assertContains(response, "Alignment Stream")
        self.assertContains(response, "All")
        self.assertContains(response, "Decisions")
        self.assertContains(response, "Open")
        self.assertContains(response, "Files")
        self.assertContains(response, self.project.name)
        self.assertContains(response, self.project.tagline)
        self.assertContains(response, "upload a reference document")
        self.assertNotContains(response, "Issues &amp; Alignment", html=True)
        self.assertNotContains(response, "Active Queue")
        self.assertContains(response, 'data-stream-input', html=False)
        self.assertContains(response, 'data-stream-drop-target', html=False)
        self.assertContains(response, 'data-stream-file-input', html=False)
        self.assertContains(response, 'data-stream-files-trigger', html=False)
        self.assertContains(response, 'data-stream-file-list', html=False)
        self.assertNotContains(response, "Upload up to 5 files. Supported: TXT, MD, PDF, DOCX. Max 20 MB each.")
        self.assertContains(response, 'data-workspace-split-root', html=False)
        self.assertContains(response, 'data-workspace-resize-handle', html=False)
        self.assertContains(response, 'data-project-settings-trigger', html=False)
        self.assertContains(response, f'/api/projects/{self.project.slug}/settings', html=False)
        self.assertContains(response, "Project identity")
        self.assertContains(response, "Preferences")
        self.assertContains(response, "Spec language")
        self.assertContains(response, "Format")
        self.assertContains(
            response,
            "Format this section using markdown formatting features such as subheadings, bullet lists, numbered lists, bold text, and emphasis where helpful. Improve scanability while preserving the original meaning, scope, and commitments.",
        )
        self.assertNotContains(response, "Ask AI to Help Draft")
        self.assertNotContains(response, "Consistency Inbox")

    def test_anonymous_workspace_renders_structured_section_html(self):
        section = section_summaries(self.project)[2]
        update_spec_section(
            project=self.project,
            section_id=section["id"],
            content_json=markdown_to_blocks("## Readiness\n\n- First pass\n- Second pass"),
        )

        response = self.client.get(reverse("project-workspace", args=[self.project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>Readiness</h2>", html=False)
        self.assertContains(response, "<li>First pass</li>", html=False)

    def test_workspace_open_filter_hides_general_posts_and_decisions(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(f"{reverse('project-workspace', args=[self.project.slug])}?stream=open")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fallback mismatch across requirements, UI/UX, and infra")
        self.assertNotContains(
            response,
            "We need each core planning area in one shared spec now. I still want magic links to be the primary direction, but contradictions across sections must be visible.",
        )
        self.assertNotContains(response, "Retain SSO, Migrate Passwords")

    def test_workspace_decisions_filter_only_shows_decisions(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(f"{reverse('project-workspace', args=[self.project.slug])}?stream=decisions")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retain SSO, Migrate Passwords")
        self.assertContains(response, "Decision Recorded")
        self.assertNotContains(
            response,
            "We need each core planning area in one shared spec now. I still want magic links to be the primary direction, but contradictions across sections must be visible.",
        )

    def test_workspace_all_filter_shows_message_attachments(self):
        self.client.force_login(self.project.created_by)
        self._create_attachment_post(
            body="Populate the spec with this.",
            filename="partner-api.txt",
            content="Partner API documentation",
        )

        response = self.client.get(reverse("project-workspace", args=[self.project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Populate the spec with this.")
        self.assertContains(response, "partner-api.txt")
        self.assertContains(response, "Download")

    def test_workspace_files_filter_only_shows_uploaded_files(self):
        self.client.force_login(self.project.created_by)
        self._create_attachment_post(
            filename="existing-spec.txt",
            content="Imported product spec",
        )

        response = self.client.get(f"{reverse('project-workspace', args=[self.project.slug])}?stream=files")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "existing-spec.txt")
        self.assertContains(response, "Download")
        self.assertNotContains(response, "Retain SSO, Migrate Passwords")
        self.assertNotContains(
            response,
            "We need each core planning area in one shared spec now. I still want magic links to be the primary direction, but contradictions across sections must be visible.",
        )

    def test_workspace_files_filter_shows_processing_badge_for_pending_uploads(self):
        self.client.force_login(self.project.created_by)
        post = self._create_attachment_post(filename="integration-guide.txt", content="Partner integration guide")
        post.processing_status = StreamPostProcessingStatus.PENDING
        post.save(update_fields=["processing_status", "updated_at"])

        response = self.client.get(f"{reverse('project-workspace', args=[self.project.slug])}?stream=files")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "integration-guide.txt")
        self.assertContains(response, "Processing")
        self.assertNotContains(response, "Processing failed")

    def test_workspace_live_fragment_renders_only_live_regions(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(
            f"{reverse('project-workspace', args=[self.project.slug])}?_fragment=workspace-live"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-workspace-header-region', html=False)
        self.assertContains(response, 'data-workspace-stream-live-region', html=False)
        self.assertContains(response, 'data-workspace-stream-scroll', html=False)
        self.assertContains(response, 'data-workspace-spec-region', html=False)
        self.assertContains(response, 'data-spec-section-form', html=False)
        self.assertContains(response, 'data-spec-scroll-container', html=False)
        self.assertNotContains(response, 'data-workspace-live-refresh-root', html=False)
        self.assertNotContains(response, 'data-workspace-split-root', html=False)
        self.assertNotContains(response, 'data-stream-input', html=False)

    def test_workspace_live_fragment_honors_stream_filter_query(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(
            f"{reverse('project-workspace', args=[self.project.slug])}?_fragment=workspace-live&stream=decisions"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retain SSO, Migrate Passwords")
        self.assertContains(response, "Decision Recorded")
        self.assertNotContains(
            response,
            "We need each core planning area in one shared spec now. I still want magic links to be the primary direction, but contradictions across sections must be visible.",
        )

    def test_workspace_live_fragment_honors_files_filter_query(self):
        self.client.force_login(self.project.created_by)
        self._create_attachment_post(filename="api-notes.txt", content="API notes")

        response = self.client.get(
            f"{reverse('project-workspace', args=[self.project.slug])}?_fragment=workspace-live&stream=files"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "api-notes.txt")
        self.assertContains(response, "Download")
        self.assertNotContains(response, "Retain SSO, Migrate Passwords")

    def test_workspace_live_fragment_honors_concern_query_without_rendering_composer(self):
        self.client.force_login(self.project.created_by)
        concern = self.project.concerns.get(title="Fallback mismatch across requirements, UI/UX, and infra")

        response = self.client.get(
            f"{reverse('project-workspace', args=[self.project.slug])}?_fragment=workspace-live&concern={concern.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Focused Concern")
        self.assertContains(response, concern.title)
        self.assertContains(response, "Address in Chat")
        self.assertContains(response, 'data-workspace-spec-region', html=False)
        self.assertNotContains(response, 'name="concern_id"', html=False)
        self.assertNotContains(response, 'data-stream-input', html=False)

    def test_workspace_live_fragment_honors_section_query_for_spec_scroll_target(self):
        self.client.force_login(self.project.created_by)
        section_id = section_summaries(self.project)[1]["id"]

        response = self.client.get(
            f"{reverse('project-workspace', args=[self.project.slug])}?_fragment=workspace-live&section={section_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-scroll-target-section="{section_id}"', html=False)
        self.assertContains(response, f'data-section-id="{section_id}"', html=False)

    def test_workspace_concern_query_focuses_thread_and_composer(self):
        self.client.force_login(self.project.created_by)
        concern = self.project.concerns.get(title="Fallback mismatch across requirements, UI/UX, and infra")

        response = self.client.get(f"{reverse('project-workspace', args=[self.project.slug])}?concern={concern.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Focused Concern")
        self.assertContains(response, concern.title)
        self.assertContains(response, 'name="concern_id"', html=False)
        self.assertContains(response, f'value="{concern.id}"', html=False)
        self.assertContains(response, "Concern thread")
        self.assertContains(response, "Address in Chat")

    def test_workspace_concern_query_renders_color_coded_diff_markup(self):
        self.client.force_login(self.project.created_by)
        concern = self.project.concerns.get(title="Fallback mismatch across requirements, UI/UX, and infra")

        response = self.client.get(f"{reverse('project-workspace', args=[self.project.slug])}?concern={concern.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Patch Review")
        self.assertContains(response, 'class="diff-view"', html=False)
        self.assertContains(response, 'class="diff-line diff-line-meta-old"', html=False)
        self.assertContains(response, 'class="diff-line diff-line-meta-new"', html=False)
        self.assertContains(response, 'class="diff-line diff-line-add"', html=False)

    def test_workspace_keeps_project_summary_out_of_document_canvas(self):
        actor = User.objects.create_user(
            username="workspace-owner",
            email="workspace-owner@example.com",
            password="SpecBridge!123",
            first_name="Workspace",
            last_name="Owner",
            title="PM",
        )
        project = create_project_workspace(
            actor=actor,
            project_name="Stats Board",
            tagline="AI assisted data collection and visualization",
        )
        project.summary = (
            "AI assisted data collection and visualization "
            "This workspace keeps documents, decisions, assumptions, and delivery intent "
            "for Stats Board aligned from the first draft onward."
        )
        project.save(update_fields=["summary", "updated_at"])
        self.client.force_login(actor)

        response = self.client.get(reverse("project-workspace", args=[project.slug]))

        self.assertContains(response, "Stats Board")
        self.assertContains(response, "Alignment Stream")
        self.assertContains(response, "AI assisted data collection and visualization")
        self.assertNotContains(
            response,
            "This workspace keeps documents, decisions, assumptions, and delivery intent for Stats Board aligned from the first draft onward.",
        )

    def test_shortcuts_redirect_to_primary_project(self):
        response = self.client.get(reverse("dashboard-shortcut"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.project.slug, response["Location"])

    def test_shortcuts_redirect_to_create_page_when_authenticated_user_has_no_projects(self):
        outsider = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="SpecBridge!123",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("dashboard-shortcut"))

        self.assertRedirects(response, reverse("project-create"))

    def test_authenticated_directory_shows_only_member_projects(self):
        outsider = User.objects.create_user(
            username="taylor",
            email="taylor@example.com",
            password="SpecBridge!123",
            first_name="Taylor",
            last_name="Ng",
            title="PM",
        )
        member_project = create_project_workspace(
            actor=outsider,
            project_name="Launch Readiness",
            tagline="Launch coordination workspace.",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("project-directory"))

        self.assertContains(response, member_project.name)
        self.assertNotContains(response, self.project.name)
        self.assertContains(response, "Select Project")
        self.assertContains(response, "Browse all projects")
        self.assertContains(response, "data-project-switcher-menu", html=False)
        self.assertContains(response, "Create Project")
        self.assertContains(response, "active workspace")
        self.assertNotContains(response, "Open Demo Project")
        self.assertNotContains(response, "Export Spec")
        self.assertNotContains(response, "Sign-in no longer falls back to the demo workspace")
        self.assertNotContains(response, "Agent-Driven Spec System")
        self.assertContains(response, "No active issues")
        self.assertNotContains(response, "Primary route")

    def test_authenticated_non_member_cannot_open_demo_workspace(self):
        outsider = User.objects.create_user(
            username="linus",
            email="linus@example.com",
            password="SpecBridge!123",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("project-workspace", args=[self.project.slug]))

        self.assertEqual(response.status_code, 404)

    def test_authenticated_directory_redirects_to_create_when_user_has_no_projects(self):
        outsider = User.objects.create_user(
            username="legacy",
            email="legacy@example.com",
            password="SpecBridge!123",
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=outsider,
            role=MembershipRole.VIEWER,
            title="Legacy viewer",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("project-directory"))

        self.assertRedirects(response, reverse("project-create"))

    def test_authenticated_legacy_demo_member_cannot_open_demo_workspace(self):
        outsider = User.objects.create_user(
            username="legacy-path",
            email="legacy-path@example.com",
            password="SpecBridge!123",
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=outsider,
            role=MembershipRole.VIEWER,
            title="Legacy viewer",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("project-workspace", args=[self.project.slug]))

        self.assertEqual(response.status_code, 404)

    def test_project_create_requires_authentication(self):
        response = self.client.get(reverse("project-create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertIn("next=/projects/create/", response["Location"])

    def test_project_create_renders_for_authenticated_user_without_projects(self):
        outsider = User.objects.create_user(
            username="new-user",
            email="new-user@example.com",
            password="SpecBridge!123",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("project-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Project")
        self.assertContains(response, "Workspace Details")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, reverse("project-create-submit"))

    def test_authenticated_user_can_create_project_via_form_submit_route(self):
        self.client.force_login(self.project.created_by)

        response = self.client.post(
            reverse("project-create-submit"),
            {
                "project_name": "Delivery Control Tower",
                "tagline": "Operations cockpit for readiness, blockers, and launches.",
            },
        )

        created_project = Project.objects.get(slug="delivery-control-tower")
        self.assertRedirects(response, reverse("project-workspace", args=[created_project.slug]))

    def test_authenticated_user_can_create_project(self):
        self.client.force_login(self.project.created_by)
        response = self.client.post(
            "/api/projects/create",
            data=json.dumps(
                {
                    "project_name": "Launch Operations Console",
                    "tagline": "Operational control plane for launch readiness and cross-functional alignment.",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        created_project = Project.objects.get(slug="launch-operations-console")

        self.assertEqual(payload["project"]["name"], "Launch Operations Console")
        self.assertEqual(payload["project"]["status_label"], "Aligning")
        self.assertEqual(payload["redirect_to"], reverse("project-workspace", args=[created_project.slug]))
        self.assertEqual(created_project.organization.name, "Sarah Stone Workspace")
        self.assertEqual(created_project.memberships.count(), 1)
        self.assertEqual(created_project.spec_document.schema_version, 2)
        self.assertEqual(created_project.spec_document.revisions.count(), 1)
        self.assertEqual(created_project.revisions.count(), 1)

        history_response = self.client.get(reverse("project-history", args=[created_project.slug]))
        self.assertEqual(history_response.status_code, 200)

    def test_authenticated_user_cannot_create_project_without_name(self):
        self.client.force_login(self.project.created_by)

        response = self.client.post(
            "/api/projects/create",
            data=json.dumps(
                {
                    "project_name": "   ",
                    "tagline": "Operational control plane for launch readiness and cross-functional alignment.",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["project_name"][0],
            "Project name is required.",
        )

    def test_authenticated_user_can_update_project_settings(self):
        actor = User.objects.create_user(
            username="settings-owner",
            email="settings-owner@example.com",
            password="SpecBridge!123",
            first_name="Settings",
            last_name="Owner",
            title="PM",
        )
        project = create_project_workspace(
            actor=actor,
            project_name="Launch Board",
            tagline="Original workspace line",
        )
        self.client.force_login(actor)

        response = self.client.post(
            f"/api/projects/{project.slug}/settings",
            data=json.dumps(
                {
                    "project_name": "Launch Control Center",
                    "tagline": "Shared source of truth for release readiness",
                    "spec_language": "tr",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.name, "Launch Control Center")
        self.assertEqual(project.tagline, "Shared source of truth for release readiness")
        self.assertEqual(project.spec_language, "tr")
        self.assertEqual(
            project.summary,
            "Shared source of truth for release readiness. "
            "This workspace keeps spec sections, decisions, assumptions, and delivery intent "
            "for Launch Control Center aligned from the first draft onward.",
        )
        self.assertEqual(response.json()["project"]["name"], "Launch Control Center")
        self.assertEqual(response.json()["project"]["tagline"], "Shared source of truth for release readiness")
        self.assertEqual(response.json()["project"]["summary"], project.summary)
        self.assertEqual(response.json()["project"]["spec_language"], "tr")

    def test_authenticated_user_cannot_update_project_settings_without_name(self):
        self.client.force_login(self.project.created_by)

        response = self.client.post(
            f"/api/projects/{self.project.slug}/settings",
            data=json.dumps(
                {
                    "project_name": "   ",
                    "tagline": "Operational control plane for launch readiness.",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["project_name"][0],
            "Project name is required.",
        )

    def test_authenticated_user_cannot_update_project_settings_with_unsupported_language(self):
        self.client.force_login(self.project.created_by)

        response = self.client.post(
            f"/api/projects/{self.project.slug}/settings",
            data=json.dumps(
                {
                    "project_name": "Launch Board",
                    "tagline": "Operational control plane for launch readiness.",
                    "spec_language": "xx",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["spec_language"][0],
            "Choose a supported spec language.",
        )

    def test_members_page_shows_invite_actions_for_pending_invites(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(reverse("project-members", args=[self.project.slug]))

        invite = self.project.invites.get(email="design@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'/api/projects/{self.project.slug}/memberships/invites/{invite.id}/resend',
            html=False,
        )
        self.assertContains(
            response,
            f'/api/projects/{self.project.slug}/memberships/invites/{invite.id}/revoke',
            html=False,
        )
        self.assertContains(response, "Last sent:")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_authenticated_user_can_resend_pending_invite(self):
        self.client.force_login(self.project.created_by)
        invite = self.project.invites.get(email="design@example.com")
        old_last_sent_at = timezone.now() - timedelta(days=1)
        invite.last_sent_at = old_last_sent_at
        invite.save(update_fields=["last_sent_at", "updated_at"])

        response = self.client.post(
            f"/api/projects/{self.project.slug}/memberships/invites/{invite.id}/resend",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(response.json()["invite"]["status"], "pending")
        self.assertGreater(invite.last_sent_at, old_last_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reminder:", mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_authenticated_user_can_create_invite_and_email_is_sent(self):
        self.client.force_login(self.project.created_by)

        response = self.client.post(
            f"/api/projects/{self.project.slug}/memberships/invite",
            data=json.dumps({"email": "new-person@example.com", "role": MembershipRole.ENGINEERING}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        invite = self.project.invites.get(email="new-person@example.com")
        self.assertIsNotNone(invite.last_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("invited you to", mail.outbox[0].subject)
        self.assertIn(invite.email, mail.outbox[0].to)
        invite_match = re.search(r"http://testserver(/invites/(?P<token>[^/]+)/)", mail.outbox[0].body)
        self.assertIsNotNone(invite_match)
        self.assertEqual(get_invite_for_token(invite_match.group("token")), invite)

    def test_authenticated_user_can_revoke_pending_invite(self):
        self.client.force_login(self.project.created_by)
        invite = self.project.invites.get(email="design@example.com")

        response = self.client.post(
            f"/api/projects/{self.project.slug}/memberships/invites/{invite.id}/revoke",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.revoked_at)
        self.assertEqual(invite.status, "revoked")
        self.assertEqual(response.json()["invite"]["status"], "revoked")

    def test_cannot_resend_non_pending_invite(self):
        self.client.force_login(self.project.created_by)
        invite = ProjectInvite.objects.create(
            project=self.project,
            email="revoked@example.com",
            role=MembershipRole.VIEWER,
            invited_by=self.project.created_by,
            last_sent_at=timezone.now() - timedelta(hours=2),
            revoked_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/memberships/invites/{invite.id}/resend",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["invite"][0],
            "Only pending invitations can be re-sent.",
        )

    def test_anonymous_accept_invite_redirects_to_login(self):
        invite = self.project.invites.get(email="design@example.com")

        response = self.client.get(reverse("project-invite-accept", args=[invitation_token(invite)]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertIn(reverse("project-invite-accept", args=[invitation_token(invite)]), response["Location"])

    def test_authenticated_matching_user_can_accept_invite(self):
        owner = User.objects.create_user(
            username="owner-user",
            email="owner@example.com",
            password="SpecBridge!123",
            first_name="Owner",
            last_name="User",
            title="PM",
        )
        private_project = create_project_workspace(
            actor=owner,
            project_name="Family Board",
            tagline="Private collaboration workspace.",
        )
        invite = ProjectInvite.objects.create(
            project=private_project,
            email="design@example.com",
            role=MembershipRole.DESIGN,
            invited_by=owner,
        )
        user = User.objects.create_user(
            username="design-user",
            email="design@example.com",
            password="SpecBridge!123",
            first_name="Design",
            last_name="User",
            title="Designer",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("project-invite-accept", args=[invitation_token(invite)]))

        self.assertRedirects(response, reverse("project-workspace", args=[private_project.slug]))
        invite.refresh_from_db()
        membership = ProjectMembership.objects.get(project=private_project, user=user)
        self.assertEqual(membership.role, invite.role)
        self.assertTrue(membership.is_active)
        self.assertIsNotNone(invite.accepted_at)

    def test_accept_invite_rejects_wrong_account(self):
        owner = User.objects.create_user(
            username="owner-two",
            email="owner-two@example.com",
            password="SpecBridge!123",
            first_name="Owner",
            last_name="Two",
            title="PM",
        )
        private_project = create_project_workspace(
            actor=owner,
            project_name="Invite Gate",
            tagline="Private invite acceptance checks.",
        )
        invite = ProjectInvite.objects.create(
            project=private_project,
            email="design@example.com",
            role=MembershipRole.DESIGN,
            invited_by=owner,
        )
        wrong_user = User.objects.create_user(
            username="wrong-user",
            email="wrong@example.com",
            password="SpecBridge!123",
        )
        self.client.force_login(wrong_user)

        response = self.client.get(reverse("project-invite-accept", args=[invitation_token(invite)]))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Sign in with the invited email address.", status_code=403)
        self.assertFalse(ProjectMembership.objects.filter(project=private_project, user=wrong_user).exists())
