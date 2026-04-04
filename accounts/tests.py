from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.demo import ensure_demo_workspace
from projects.models import MembershipRole, Organization, ProjectMembership

User = get_user_model()


class AuthenticationFlowTests(TestCase):
    def test_project_pages_are_public(self):
        project = ensure_demo_workspace()

        directory_response = self.client.get(reverse("project-directory"))
        workspace_response = self.client.get(reverse("project-workspace", args=[project.slug]))

        self.assertEqual(directory_response.status_code, 200)
        self.assertContains(directory_response, "Read-only")
        self.assertEqual(workspace_response.status_code, 200)

    def test_signup_creates_user_logs_in_without_demo_membership(self):
        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "username": "ada",
                "email": "ada@example.com",
                "organization": "Analogue Labs",
                "title": "PM",
                "password1": "SpecBridge!123",
                "password2": "SpecBridge!123",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("project-create"))
        user = User.objects.get(username="ada")
        organization = Organization.objects.get(name="Analogue Labs")
        self.assertFalse(ProjectMembership.objects.filter(user=user).exists())
        self.assertEqual(organization.slug, "analogue-labs")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertContains(response, "Workspace Details")
        self.assertNotContains(response, "Authentication Revamp")

    def test_login_accepts_email_and_honors_next_redirect(self):
        ensure_demo_workspace()
        response = self.client.post(
            reverse("login"),
            {
                "username": "sarah@example.com",
                "password": "specbridge",
                "next": reverse("project-directory"),
            },
        )

        self.assertRedirects(response, reverse("project-directory"))
        self.assertEqual(self.client.session["_auth_user_id"], str(User.objects.get(username="sarah").pk))

    def test_login_ignores_demo_next_for_non_demo_user_with_legacy_membership(self):
        project = ensure_demo_workspace()
        user = User.objects.create_user(
            username="casey",
            email="casey@example.com",
            password="SpecBridge!123",
        )
        ProjectMembership.objects.create(
            project=project,
            user=user,
            role=MembershipRole.VIEWER,
            title="Legacy viewer",
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "casey",
                "password": "SpecBridge!123",
                "next": reverse("project-workspace", args=[project.slug]),
            },
        )

        self.assertRedirects(response, reverse("project-create"))

    def test_ajax_login_returns_json_and_logs_user_in(self):
        ensure_demo_workspace()
        response = self.client.post(
            reverse("login"),
            {
                "username": "sarah",
                "password": "specbridge",
                "next": reverse("project-directory"),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"ok": True, "redirect_to": reverse("project-directory")},
        )
        self.assertEqual(self.client.session["_auth_user_id"], str(User.objects.get(username="sarah").pk))

    def test_logout_redirects_back_to_requested_public_page(self):
        project = ensure_demo_workspace()
        self.client.post(reverse("login"), {"username": "sarah", "password": "specbridge"})

        response = self.client.post(
            reverse("logout"),
            {"next": reverse("project-workspace", args=[project.slug])},
        )

        self.assertRedirects(response, reverse("project-workspace", args=[project.slug]))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_api_is_public(self):
        project = ensure_demo_workspace()

        response = self.client.get(f"/api/projects/{project.slug}/stats")

        self.assertEqual(response.status_code, 200)

    def test_mutating_api_requires_authenticated_session(self):
        project = ensure_demo_workspace()

        response = self.client.post(
            f"/api/projects/{project.slug}/memberships/invite",
            data='{"email":"teammate@example.com","role":"viewer"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
