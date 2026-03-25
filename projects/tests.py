import json

from django.test import Client, TestCase
from django.urls import reverse

from projects.demo import ensure_demo_workspace
from projects.models import Project


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
