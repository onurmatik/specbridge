import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from projects.demo import ensure_demo_workspace
from projects.models import MembershipRole, Project, ProjectMembership
from projects.services import create_project_workspace

User = get_user_model()


class ProjectPageTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()

    def test_project_directory_renders(self):
        response = self.client.get(reverse("project-directory"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agent-Driven Spec System")
        self.assertContains(response, self.project.name)
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

    def test_authenticated_workspace_renders_unified_spec_and_issues_rail(self):
        self.client.force_login(self.project.created_by)

        response = self.client.get(reverse("project-workspace", args=[self.project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-api-method="PATCH"', html=False)
        self.assertContains(response, 'data-spec-section-form', html=False)
        self.assertContains(response, 'data-spec-section-input', html=False)
        self.assertContains(response, 'data-spec-nav-link', html=False)
        self.assertContains(response, 'data-spec-nav-fade-left', html=False)
        self.assertContains(response, "Alignment Stream")
        self.assertContains(response, "All")
        self.assertContains(response, "Decisions")
        self.assertContains(response, "Open")
        self.assertContains(response, self.project.name)
        self.assertContains(response, self.project.tagline)
        self.assertContains(response, "Add to the discussion or propose a decision...")
        self.assertNotContains(response, "Issues &amp; Alignment", html=True)
        self.assertNotContains(response, "Active Queue")
        self.assertContains(response, 'data-stream-input', html=False)
        self.assertNotContains(response, "Ask AI to Help Draft")
        self.assertNotContains(response, "Consistency Inbox")

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
        self.assertNotContains(response, "Open Demo Project")

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
        self.assertEqual(created_project.spec_document.schema_version, 1)
        self.assertEqual(created_project.spec_document.revisions.count(), 1)
        self.assertEqual(created_project.revisions.count(), 1)

        history_response = self.client.get(reverse("project-history", args=[created_project.slug]))
        self.assertEqual(history_response.status_code, 200)
