import json

from django.test import Client, TestCase

from alignment.models import Decision, DecisionStatus, OpenQuestion, StreamPost
from projects.demo import ensure_demo_workspace


class AlignmentApiTests(TestCase):
    def setUp(self):
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
        self.assertTrue(StreamPost.objects.filter(project=self.project, body="Need a fast draft for infra ownership.").exists())

    def test_create_stream_post_requires_body(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data=json.dumps({"body": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["errors"]["body"], ["Message is required."])
