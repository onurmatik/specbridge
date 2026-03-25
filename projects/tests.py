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

    def test_shortcuts_redirect_to_primary_project(self):
        response = self.client.get(reverse("dashboard-shortcut"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.project.slug, response["Location"])

    def test_shortcuts_redirect_to_directory_when_authenticated_user_has_no_projects(self):
        outsider = User.objects.create_user(
            username="grace",
            email="grace@example.com",
            password="SpecBridge!123",
        )
        self.client.force_login(outsider)

        response = self.client.get(reverse("dashboard-shortcut"))

        self.assertRedirects(response, reverse("project-directory"))

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

    def test_authenticated_directory_hides_demo_even_with_legacy_membership(self):
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

        self.assertNotContains(response, self.project.name)
        self.assertContains(response, "No projects yet")

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
        self.assertEqual(created_project.sections.count(), 5)
        self.assertEqual(created_project.versions.count(), 1)

        history_response = self.client.get(reverse("project-history", args=[created_project.slug]))
        self.assertEqual(history_response.status_code, 200)
