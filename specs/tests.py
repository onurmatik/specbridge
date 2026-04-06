import json
from unittest.mock import patch

from django.test import Client, TestCase

from projects.demo import ensure_demo_workspace
from specs.concerns import ConcernAnalysisResult, ConcernProposalResult, ConcernReevaluationResult
from specs.models import Assumption, ConcernProposalChange, ConcernRun, ProjectConcern, ProjectDocument
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

    def test_document_update_noop_does_not_create_revisions(self):
        document = ProjectDocument.objects.get(project=self.project, slug="requirements")
        project_revision_count = self.project.revisions.count()
        document_revision_count = document.revisions.count()

        update_document(document=document, body=document.body)

        self.assertEqual(self.project.revisions.count(), project_revision_count)
        document.refresh_from_db()
        self.assertEqual(document.revisions.count(), document_revision_count)

    def test_document_update_marks_linked_concern_stale_and_queues_recheck(self):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="fallback-mismatch")
        document = ProjectDocument.objects.get(project=self.project, slug="requirements")

        update_document(document=document, body=f"{document.body}\n\nAligned fallback language.")

        concern.refresh_from_db()
        self.assertEqual(concern.status, "stale")
        self.assertIsNotNone(concern.reevaluation_requested_at)
        self.assertTrue(
            ConcernRun.objects.filter(
                project=self.project,
                status="pending",
                target_concern_fingerprint=concern.fingerprint,
            ).exists()
        )

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

    @patch("specs.concerns.analyze_project_concerns")
    def test_create_concern_run_endpoint_upserts_ai_concerns(self, mock_analyze):
        mock_analyze.return_value = ConcernAnalysisResult(
            provider="openai",
            model="gpt-5-mini",
            concerns=[
                {
                    "concern_type": "usability",
                    "fingerprint": "ui-fallback-copy",
                    "title": "Fallback copy is still too vague",
                    "summary": "The UI/UX doc does not define the exact copy for delayed delivery.",
                    "severity": "medium",
                    "recommendation": "Spell out the fallback copy and escalation language.",
                    "source_refs": [
                        {"kind": "document", "identifier": "ui-ux", "label": "UI/UX"},
                    ],
                }
            ],
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concern-runs",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        concern = ProjectConcern.objects.get(project=self.project, fingerprint__isnull=False, title="Fallback copy is still too vague")
        self.assertEqual(concern.concern_type, "usability")
        self.assertEqual(concern.status, "open")

    @patch("specs.concerns.reevaluate_concern_with_ai")
    def test_re_evaluate_concern_endpoint_updates_status(self, mock_reevaluate):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")
        mock_reevaluate.return_value = ConcernReevaluationResult(
            provider="openai",
            model="gpt-5-mini",
            status="resolved",
            title=concern.title,
            summary="Ownership is now clear in the linked documents.",
            severity="low",
            recommendation="Keep the owner listed in requirements and infra.",
            source_refs=[
                {"kind": "document", "identifier": "requirements", "label": "Requirements"},
                {"kind": "document", "identifier": "infra", "label": "Infra"},
            ],
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concerns/{concern.id}/re-evaluate",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        concern.refresh_from_db()
        self.assertEqual(concern.status, "resolved")

    @patch("specs.concerns.build_concern_proposal_with_ai")
    def test_resolve_concern_with_ai_endpoint_creates_reviewable_proposal(self, mock_build_proposal):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")
        mock_build_proposal.return_value = ConcernProposalResult(
            provider="openai",
            model="gpt-5-mini",
            summary="Apply one ownership note to requirements and infra.",
            changes=[
                {
                    "document_slug": "requirements",
                    "summary": "Name the fallback owner in requirements.",
                    "proposed_body": "Updated requirements body",
                },
                {
                    "document_slug": "infra",
                    "summary": "Mirror the same owner in infra.",
                    "proposed_body": "Updated infra body",
                },
            ],
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concerns/{concern.id}/resolve-with-ai",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        concern.refresh_from_db()
        proposal = concern.proposals.first()
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.changes.count(), 2)

    def test_accepting_proposal_change_updates_document_and_marks_concern_stale(self):
        change = ConcernProposalChange.objects.select_related("proposal__concern", "document").first()
        document_revision_count = change.document.revisions.count()

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concern-proposals/{change.proposal_id}/changes/{change.id}/accept",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        self.assertEqual(change.status, "accepted")
        change.document.refresh_from_db()
        self.assertEqual(change.document.body, change.proposed_body)
        self.assertEqual(change.document.revisions.count(), document_revision_count + 1)
        change.proposal.concern.refresh_from_db()
        self.assertEqual(change.proposal.concern.status, "stale")
