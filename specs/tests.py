import json

from django.test import Client, TestCase

from projects.demo import ensure_demo_workspace
from specs.models import Assumption, SpecSection
from specs.services import compare_versions, update_section


class SpecsServiceTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def test_section_update_creates_new_version(self):
        section = SpecSection.objects.get(project=self.project, key="solution")
        version_count = self.project.versions.count()
        update_section(section=section, body=f"{section.body}\n\nExtra detail.")
        self.assertEqual(self.project.versions.count(), version_count + 1)

    def test_compare_versions_returns_changes(self):
        versions = list(self.project.versions.order_by("number"))
        rows = compare_versions(versions[1], versions[2])
        self.assertTrue(any(row["change"] != "unchanged" for row in rows))

    def test_create_and_validate_assumption_endpoints(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/assumptions",
            data=json.dumps(
                {
                    "title": "New assumption",
                    "description": "A test assumption",
                    "section_key": "solution",
                    "impact": "medium",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        assumption = Assumption.objects.get(title="New assumption")
        validate = self.client.post(
            f"/api/projects/{self.project.slug}/assumptions/{assumption.id}/validate",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(validate.status_code, 200)
        assumption.refresh_from_db()
        self.assertEqual(assumption.status, "validated")
