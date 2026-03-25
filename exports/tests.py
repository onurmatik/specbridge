import json

from django.test import Client, TestCase

from exports.models import ExportArtifact
from projects.demo import ensure_demo_workspace


class ExportApiTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def test_export_creation_endpoint(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/exports",
            data=json.dumps({"format": "agent", "extension": "md", "share_enabled": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ExportArtifact.objects.filter(project=self.project, format="agent").exists())
