import json
from unittest.mock import patch

from django.test import Client, TestCase

from projects.demo import ensure_demo_workspace
from specs.concerns import ConcernAnalysisResult, ConcernProposalResult, ConcernReevaluationResult
from specs.models import Assumption, ConcernProposalChange, ConcernRun, ProjectConcern
from specs.section_ai import _section_revision_prompt
from specs.services import (
    add_spec_section_after,
    delete_spec_section,
    reorder_spec_section,
    section_markdown_for_ref,
    section_summaries,
    update_spec_section,
)
from specs.spec_document import markdown_to_blocks


class SpecsServiceTests(TestCase):
    def setUp(self):
        self.project = ensure_demo_workspace()
        self.client = Client()
        self.client.force_login(self.project.created_by)

    def _section(self, key):
        self.project.refresh_from_db()
        return next(section for section in section_summaries(self.project) if section["key"] == key)

    def _section_keys(self):
        self.project.refresh_from_db()
        return [section["key"] for section in section_summaries(self.project)]

    def test_section_update_creates_new_revisions(self):
        section = self._section("requirements")
        project_revision_count = self.project.revisions.count()
        spec_revision_count = self.project.spec_document.revisions.count()

        update_spec_section(
            project=self.project,
            section_id=section["id"],
            content_json=markdown_to_blocks(f"{section['body']}\n\nExtra detail."),
        )

        self.assertEqual(self.project.revisions.count(), project_revision_count + 1)
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.revisions.count(), spec_revision_count + 1)

    def test_section_update_noop_does_not_create_revisions(self):
        section = self._section("requirements")
        project_revision_count = self.project.revisions.count()
        spec_revision_count = self.project.spec_document.revisions.count()

        update_spec_section(
            project=self.project,
            section_id=section["id"],
            content_json=markdown_to_blocks(section["body"]),
        )

        self.assertEqual(self.project.revisions.count(), project_revision_count)
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.revisions.count(), spec_revision_count)

    def test_add_spec_section_after_inserts_custom_section_and_creates_revisions(self):
        section = self._section("overview")
        project_revision_count = self.project.revisions.count()
        spec_revision_count = self.project.spec_document.revisions.count()

        inserted_section = add_spec_section_after(
            project=self.project,
            after_section_id=section["id"],
            title="Edge Cases",
        )

        self.assertEqual(inserted_section["title"], "Edge Cases")
        self.assertEqual(inserted_section["kind"], "custom")
        self.assertEqual(
            self._section_keys()[:3],
            ["overview", "edge-cases", "goals"],
        )
        self.assertEqual(self.project.revisions.count(), project_revision_count + 1)
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.revisions.count(), spec_revision_count + 1)

    def test_reorder_spec_section_moves_section_and_creates_revisions(self):
        section = self._section("requirements")
        project_revision_count = self.project.revisions.count()
        spec_revision_count = self.project.spec_document.revisions.count()

        moved_section = reorder_spec_section(
            project=self.project,
            section_id=section["id"],
            direction="up",
        )

        self.assertEqual(moved_section["id"], section["id"])
        self.assertEqual(
            self._section_keys()[:3],
            ["overview", "requirements", "goals"],
        )
        self.assertEqual(self.project.revisions.count(), project_revision_count + 1)
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.revisions.count(), spec_revision_count + 1)

    def test_delete_spec_section_removes_section_and_marks_linked_concern_stale(self):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="fallback-mismatch")
        section = self._section("requirements")
        project_revision_count = self.project.revisions.count()
        spec_revision_count = self.project.spec_document.revisions.count()

        result = delete_spec_section(project=self.project, section_id=section["id"])

        self.assertEqual(result["deleted_section"]["id"], section["id"])
        self.assertNotIn("requirements", self._section_keys())
        self.assertEqual(self.project.revisions.count(), project_revision_count + 1)
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.revisions.count(), spec_revision_count + 1)

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

    def test_section_update_marks_linked_concern_stale_and_queues_recheck(self):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="fallback-mismatch")
        section = self._section("requirements")

        update_spec_section(
            project=self.project,
            section_id=section["id"],
            content_json=markdown_to_blocks(f"{section['body']}\n\nAligned fallback language."),
        )

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

    def test_spec_revisions_endpoint_returns_items(self):
        response = self.client.get(f"/api/projects/{self.project.slug}/spec/revisions")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["items"])

    @patch("specs.section_ai._request_openai")
    def test_section_ai_revision_endpoint_returns_revised_body(self, mock_request_openai):
        section = self._section("requirements")
        mock_request_openai.return_value = (
            "gpt-5-mini",
            {
                "summary": "Tightened the wording and cleaned up repetition.",
                "revised_body": "Revised requirements body",
            },
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}/revise-with-ai",
            data=json.dumps(
                {
                    "prompt": "Clarify this section and make it easier to scan.",
                    "title": section["title"],
                    "body": section["body"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["prompt"], "Clarify this section and make it easier to scan.")
        self.assertEqual(payload["body"], "Revised requirements body")
        self.assertEqual(payload["summary"], "Tightened the wording and cleaned up repetition.")

    def test_section_ai_revision_endpoint_rejects_empty_prompt(self):
        section = self._section("requirements")

        response = self.client.post(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}/revise-with-ai",
            data=json.dumps(
                {
                    "prompt": "   ",
                    "title": section["title"],
                    "body": section["body"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["section"][0],
            "Enter a revision prompt before running AI.",
        )

    def test_insert_section_endpoint_creates_new_section(self):
        section = self._section("overview")

        response = self.client.post(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}/insert-below",
            data=json.dumps({"title": "Release Plan"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "Release Plan")
        self.assertEqual(
            self._section_keys()[:3],
            ["overview", "release-plan", "goals"],
        )

    def test_move_section_endpoint_rejects_invalid_boundary_move(self):
        section = self._section("overview")

        response = self.client.post(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}/move",
            data=json.dumps({"direction": "up"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["section"][0],
            "Section cannot be moved further.",
        )

    def test_delete_section_endpoint_returns_next_focus_section(self):
        section = self._section("requirements")
        next_section = self._section("ui-ux")

        response = self.client.delete(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deleted_section_id"], section["id"])
        self.assertEqual(payload["focus_section_id"], next_section["id"])

    def test_section_ai_prompt_requires_english_output(self):
        prompt = _section_revision_prompt(
            prompt="Bunu daha net yaz.",
            title="Requirements",
            kind="requirements",
            status="iterating",
            body="Gecikmeli e-posta teslimatı durumunda kullanıcıya açık bir yönlendirme göster.",
        )

        self.assertIn("Always return the revised section and summary in English", prompt)

    def test_create_and_validate_assumption_endpoints(self):
        section = self._section("requirements")
        response = self.client.post(
            f"/api/projects/{self.project.slug}/assumptions",
            data=json.dumps(
                {
                    "title": "New assumption",
                    "description": "A test assumption",
                    "section_id": section["id"],
                    "impact": "medium",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        assumption = Assumption.objects.get(title="New assumption")
        self.assertEqual(assumption.primary_ref["section_id"], section["id"])
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
                    "summary": "The UI/UX section does not define the exact copy for delayed delivery.",
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
        self.assertTrue(concern.node_refs)

    @patch("specs.concerns.reevaluate_concern_with_ai")
    def test_re_evaluate_concern_endpoint_updates_status(self, mock_reevaluate):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")
        mock_reevaluate.return_value = ConcernReevaluationResult(
            provider="openai",
            model="gpt-5-mini",
            status="resolved",
            title=concern.title,
            summary="Ownership is now clear in the linked sections.",
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
        self.assertEqual(len(concern.node_refs), 2)

    @patch("specs.concerns.build_concern_proposal_with_ai")
    def test_resolve_concern_with_ai_endpoint_creates_reviewable_proposal(self, mock_build_proposal):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")
        requirements_section = self._section("requirements")
        infra_section = self._section("infra")
        mock_build_proposal.return_value = ConcernProposalResult(
            provider="openai",
            model="gpt-5-mini",
            summary="Apply one ownership note to requirements and infra.",
            changes=[
                {
                    "section_id": requirements_section["id"],
                    "summary": "Name the fallback owner in requirements.",
                    "proposed_body": "Updated requirements body",
                },
                {
                    "section_id": infra_section["id"],
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
        self.assertEqual(
            set(proposal.changes.values_list("section_id", flat=True)),
            {requirements_section["id"], infra_section["id"]},
        )

    def test_accepting_proposal_change_updates_section_and_marks_concern_stale(self):
        change = ConcernProposalChange.objects.select_related("proposal__concern").first()
        spec_revision_count = self.project.spec_document.revisions.count()

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concern-proposals/{change.proposal_id}/changes/{change.id}/accept",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        self.assertEqual(change.status, "accepted")
        self.project.refresh_from_db()
        self.assertEqual(
            section_markdown_for_ref(self.project, {"section_id": change.section_id}).strip(),
            change.proposed_body.strip(),
        )
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.revisions.count(), spec_revision_count + 1)
        change.proposal.concern.refresh_from_db()
        self.assertEqual(change.proposal.concern.status, "stale")
