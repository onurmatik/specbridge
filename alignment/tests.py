import json

from django.test import Client, TestCase

from alignment.models import Decision, DecisionStatus, OpenQuestion, StreamPost
from projects.demo import ensure_demo_workspace
from specs.models import ProjectConcern


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

    def test_create_stream_post_requires_body(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/stream",
            data=json.dumps({"body": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["errors"]["body"], ["Message is required."])
