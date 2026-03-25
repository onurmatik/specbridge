import json

from django.test import Client, TestCase

from agents.models import AgentSuggestion, AgentSuggestionStatus
from projects.demo import ensure_demo_workspace


class AgentApiTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def test_apply_suggestion_endpoint(self):
        suggestion = AgentSuggestion.objects.get(title="Clarify delayed-email fallback")
        response = self.client.post(
            f"/api/projects/{self.project.slug}/agent-suggestions/{suggestion.id}/apply",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, AgentSuggestionStatus.APPLIED)
