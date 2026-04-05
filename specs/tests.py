import json
from unittest.mock import patch

from django.test import Client, TestCase

from projects.demo import ensure_demo_workspace
from specs.consistency import ConsistencyAnalysisResult, ConsistencyError, dismiss_consistency_issue
from specs.models import Assumption, ConsistencyIssue, ProjectDocument
from specs.services import update_document


class SpecsServiceTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def test_document_update_creates_new_revisions(self):
        document = ProjectDocument.objects.get(project=self.project, slug="requirements")
        project_revision_count = self.project.revisions.count()
        document_revision_count = document.revisions.count()

        update_document(document=document, body=f"{document.body}\n\nExtra detail.")

        self.assertEqual(self.project.revisions.count(), project_revision_count + 1)
        document.refresh_from_db()
        self.assertEqual(document.revisions.count(), document_revision_count + 1)

    def test_document_revisions_endpoint_returns_items(self):
        response = self.client.get(f"/api/projects/{self.project.slug}/documents/requirements/revisions")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["items"])

    def test_create_and_validate_assumption_endpoints(self):
        response = self.client.post(
            f"/api/projects/{self.project.slug}/assumptions",
            data=json.dumps(
                {
                    "title": "New assumption",
                    "description": "A test assumption",
                    "document_slug": "requirements",
                    "impact": "medium",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        assumption = Assumption.objects.get(title="New assumption")
        self.assertEqual(assumption.document.slug, "requirements")
        validate = self.client.post(
            f"/api/projects/{self.project.slug}/assumptions/{assumption.id}/validate",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(validate.status_code, 200)
        assumption.refresh_from_db()
        self.assertEqual(assumption.status, "validated")

    @patch("specs.consistency.analyze_project_consistency")
    def test_create_consistency_run_endpoint_upserts_and_reopens_issues(self, mock_analyze):
        mock_analyze.return_value = ConsistencyAnalysisResult(
            provider="openai",
            model="gpt-5-mini",
            issues=[
                {
                    "fingerprint": "requirements-infra-fallback",
                    "title": "Fallback mismatch",
                    "summary": "Requirements and infra disagree about delayed email recovery.",
                    "severity": "high",
                    "recommendation": "Normalize the fallback flow across both docs.",
                    "source_refs": [
                        {"kind": "document", "identifier": "requirements", "label": "Requirements"},
                        {"kind": "document", "identifier": "infra", "label": "Infra"},
                    ],
                }
            ],
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/consistency-runs",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        issue = ConsistencyIssue.objects.get(fingerprint__isnull=False, title="Fallback mismatch")
        self.assertEqual(issue.status, "open")

        dismiss_consistency_issue(issue=issue, actor=self.project.created_by)
        response = self.client.post(
            f"/api/projects/{self.project.slug}/consistency-runs",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, "open")

    @patch("specs.consistency.analyze_project_consistency")
    def test_create_consistency_run_endpoint_records_failures(self, mock_analyze):
        mock_analyze.side_effect = ConsistencyError("boom")

        response = self.client.post(
            f"/api/projects/{self.project.slug}/consistency-runs",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
