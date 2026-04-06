import json

from django.test import Client, TestCase

from exports.models import ExportArtifact
from projects.demo import ensure_demo_workspace
from specs.services import section_summaries


class ExportApiTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def test_export_creation_endpoint(self):
        section_ids = ",".join(section["id"] for section in section_summaries(self.project)[:2])
        response = self.client.post(
            f"/api/projects/{self.project.slug}/exports",
            data=json.dumps(
                {
                    "format": "agent",
                    "extension": "md",
                    "share_enabled": True,
                    "section_ids": section_ids,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        artifact = ExportArtifact.objects.get(project=self.project, format="agent")
        self.assertEqual(artifact.configuration["section_ids"], section_ids)
