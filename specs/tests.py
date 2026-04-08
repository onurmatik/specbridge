import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.demo import ensure_demo_workspace
from specs.concerns import (
    ConcernAnalysisResult,
    ConcernError,
    ConcernProposalResult,
    ConcernReevaluationResult,
    _request_openai,
    build_concern_proposal_with_ai,
    run_project_concerns,
)
from specs.consistency import run_project_consistency
from specs.models import Assumption, ConcernProposalChange, ConcernRun, ProjectConcern
from specs.models import AIUsageRecord
from specs.section_ai import _section_revision_prompt, revise_section_with_ai
from specs.services import (
    add_spec_section_after,
    delete_spec_section,
    reorder_spec_section,
    section_markdown_for_ref,
    section_summaries,
    update_spec_section,
)
from specs.spec_document import blocks_to_markdown, markdown_to_blocks
from specs.templatetags.specs_formatting import render_spec_blocks, render_unified_diff


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class DiffFormattingTests(TestCase):
    def test_render_unified_diff_applies_expected_line_classes(self):
        html = render_unified_diff("--- old\n+++ new\n@@ -1 +1 @@\n-removed\n+added\n unchanged")

        self.assertIn('class="diff-line diff-line-meta-old"', html)
        self.assertIn('class="diff-line diff-line-meta-new"', html)
        self.assertIn('class="diff-line diff-line-hunk"', html)
        self.assertIn('class="diff-line diff-line-remove"', html)
        self.assertIn('class="diff-line diff-line-add"', html)
        self.assertIn('class="diff-line diff-line-context"', html)


class SpecDocumentFormattingTests(TestCase):
    def test_markdown_round_trip_preserves_headings_and_nested_lists(self):
        markdown = "## Rollout\n\n1. **Primary** flow\n  - *Monitor* alerts\n  - Update docs\n\n### Notes\n\n- Keep ***fallback***"

        blocks = markdown_to_blocks(markdown)

        self.assertEqual(blocks_to_markdown(blocks), markdown)

    def test_render_spec_blocks_renders_lists_inline_marks_and_escapes_html(self):
        html = render_spec_blocks(markdown_to_blocks("## Rollout\n\n1. **Launch**\n  - *<script>alert(1)</script>*"))

        self.assertIn("<h2>Rollout</h2>", html)
        self.assertIn("<ol>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<strong>Launch</strong>", html)
        self.assertIn("<em>&lt;script&gt;alert(1)&lt;/script&gt;</em>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)


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

    def test_section_summary_hides_redundant_leading_heading(self):
        section = self._section("overview")

        update_spec_section(
            project=self.project,
            section_id=section["id"],
            content_json=markdown_to_blocks("Overview\n\nActual overview body"),
        )

        self.assertEqual(self._section("overview")["body"], "Actual overview body")

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

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("specs.openai.request.urlopen")
    def test_section_ai_revision_records_token_usage(self, mock_urlopen):
        section = self._section("requirements")
        mock_urlopen.return_value = _FakeHTTPResponse(
            {
                "id": "resp_section",
                "status": "completed",
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 45,
                    "total_tokens": 165,
                    "input_tokens_details": {"cached_tokens": 25},
                    "output_tokens_details": {"reasoning_tokens": 18},
                },
                "output_text": json.dumps(
                    {
                        "summary": "Refined the section.",
                        "revised_body": "Updated requirements body",
                    }
                ),
            }
        )

        result = revise_section_with_ai(
            project=self.project,
            section_id=section["id"],
            actor=self.project.created_by,
            prompt="Clarify the section.",
            title=section["title"],
            body=section["body"],
        )

        self.assertEqual(result.revised_body, "Updated requirements body")
        usage = AIUsageRecord.objects.get(operation="section_revision")
        self.assertEqual(usage.project, self.project)
        self.assertEqual(usage.organization, self.project.organization)
        self.assertEqual(usage.user, self.project.created_by)
        self.assertEqual(usage.input_tokens, 120)
        self.assertEqual(usage.output_tokens, 45)
        self.assertEqual(usage.reasoning_tokens, 18)
        self.assertEqual(usage.cached_input_tokens, 25)
        self.assertEqual(usage.total_tokens, 165)
        self.assertEqual(usage.context_metadata["section_id"], section["id"])

    @patch("specs.section_ai._request_openai")
    def test_section_ai_revision_strips_redundant_leading_heading(self, mock_request_openai):
        section = self._section("requirements")
        mock_request_openai.return_value = (
            "gpt-5-mini",
            {
                "summary": "Refined the section.",
                "revised_body": "# Requirements\n\nUpdated requirements body",
            },
        )

        result = revise_section_with_ai(
            project=self.project,
            section_id=section["id"],
            prompt="Clarify the section.",
            title=section["title"],
            body=section["body"],
        )

        self.assertEqual(result.revised_body, "Updated requirements body")

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

    def test_patch_section_endpoint_accepts_content_json_payload(self):
        section = self._section("requirements")
        content_json = [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Acceptance"}],
            },
            {
                "type": "orderedList",
                "attrs": {"start": 1},
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Primary flow"}],
                            },
                            {
                                "type": "bulletList",
                                "content": [
                                    {
                                        "type": "listItem",
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [{"type": "text", "text": "Nested detail"}],
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
        ]

        response = self.client.patch(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}",
            data=json.dumps({"content_json": content_json}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        updated_section = self._section("requirements")
        self.assertEqual(updated_section["blocks"], content_json)
        self.assertEqual(
            updated_section["body"],
            "## Acceptance\n\n1. Primary flow\n  - Nested detail",
        )
        self.project.spec_document.refresh_from_db()
        self.assertEqual(self.project.spec_document.schema_version, 2)

    def test_patch_section_endpoint_persists_inline_marks(self):
        section = self._section("requirements")
        content_json = [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Bold",
                        "marks": [{"type": "bold"}],
                    },
                    {
                        "type": "text",
                        "text": " and ",
                    },
                    {
                        "type": "text",
                        "text": "italic",
                        "marks": [{"type": "italic"}],
                    },
                    {
                        "type": "text",
                        "text": " text",
                    },
                ],
            }
        ]

        response = self.client.patch(
            f"/api/projects/{self.project.slug}/spec/sections/{section['id']}",
            data=json.dumps({"content_json": content_json}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        updated_section = self._section("requirements")
        self.assertEqual(updated_section["blocks"], content_json)
        self.assertEqual(updated_section["body"], "**Bold** and *italic* text")
        self.assertIn("<strong>Bold</strong>", render_spec_blocks(updated_section["blocks"]))
        self.assertIn("<em>italic</em>", render_spec_blocks(updated_section["blocks"]))

    def test_history_and_handoff_render_structured_blocks(self):
        section = self._section("requirements")
        update_spec_section(
            project=self.project,
            section_id=section["id"],
            content_json=markdown_to_blocks("## Readiness\n\n1. Primary flow\n  - Nested detail"),
        )

        history_response = self.client.get(f"{reverse('project-history', args=[self.project.slug])}?section={section['id']}")
        handoff_response = self.client.get(reverse("project-handoff", args=[self.project.slug]))

        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(handoff_response.status_code, 200)
        self.assertContains(history_response, "<h2>Readiness</h2>", html=False)
        self.assertContains(history_response, "Nested detail")
        self.assertContains(handoff_response, "<h2>Readiness</h2>", html=False)
        self.assertContains(handoff_response, "Nested detail")

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

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("specs.openai.request.urlopen")
    def test_run_project_concerns_records_token_usage(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHTTPResponse(
            {
                "id": "resp_concern",
                "status": "completed",
                "usage": {
                    "input_tokens": 300,
                    "output_tokens": 90,
                    "total_tokens": 390,
                    "output_tokens_details": {"reasoning_tokens": 44},
                },
                "output_text": json.dumps({"concerns": []}),
            }
        )

        run = run_project_concerns(self.project, actor=self.project.created_by)

        usage = AIUsageRecord.objects.get(operation="concern_scan")
        self.assertEqual(usage.project, self.project)
        self.assertEqual(usage.user, self.project.created_by)
        self.assertEqual(usage.concern_run, run)
        self.assertEqual(usage.input_tokens, 300)
        self.assertEqual(usage.output_tokens, 90)
        self.assertEqual(usage.reasoning_tokens, 44)
        self.assertEqual(usage.total_tokens, 390)
        self.assertEqual(usage.context_metadata["trigger"], "manual")

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

    @patch("specs.concerns.build_concern_proposal_with_ai")
    def test_resolve_concern_with_ai_endpoint_returns_validation_error(self, mock_build_proposal):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")
        mock_build_proposal.side_effect = ConcernError("AI could not produce a valid proposal.")

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concerns/{concern.id}/resolve-with-ai",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["errors"]["concern"][0],
            "AI could not produce a valid proposal.",
        )

    @patch("specs.concerns.build_concern_proposal_with_ai")
    def test_resolve_concern_with_ai_endpoint_falls_back_to_full_spec_for_unlinked_concern(self, mock_build_proposal):
        requirements_section = self._section("requirements")
        concern = ProjectConcern.objects.create(
            project=self.project,
            fingerprint="business-model-unclear",
            concern_type="human_flag",
            raised_by_kind="human",
            title="Business model needs clarification",
            summary="We need to clarify the business model.",
            severity="medium",
            status="open",
            recommendation="Clarify the monetization and pricing assumptions in the spec.",
            source_refs=[{"kind": "stream_post", "identifier": "999", "label": "Activity post #999"}],
            node_refs=[],
            created_by=self.project.created_by,
        )
        mock_build_proposal.return_value = ConcernProposalResult(
            provider="openai",
            model="gpt-5-mini",
            summary="Add monetization guidance to the requirements.",
            changes=[
                {
                    "section_id": requirements_section["id"],
                    "summary": "Add business model detail.",
                    "proposed_body": "Updated requirements body",
                }
            ],
        )

        response = self.client.post(
            f"/api/projects/{self.project.slug}/concerns/{concern.id}/resolve-with-ai",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        sections = mock_build_proposal.call_args.args[2]
        self.assertEqual(
            {section["id"] for section in sections},
            {section["id"] for section in section_summaries(self.project)},
        )
        concern.refresh_from_db()
        self.assertEqual(
            {ref["section_id"] for ref in concern.node_refs},
            {requirements_section["id"]},
        )

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("specs.openai.request.urlopen")
    def test_request_openai_reports_incomplete_json_schema_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHTTPResponse(
            {
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output_text": "{\"summary\":\"cut off",
            }
        )

        with self.assertRaisesMessage(
            ConcernError,
            "OpenAI response was incomplete (reason: max_output_tokens).",
        ):
            _request_openai(
                schema_name="test_schema",
                schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                },
                prompt="Return a summary.",
            )

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_CONCERN_PROPOSAL_MAX_OUTPUT_TOKENS=4321)
    @patch("specs.openai.request.urlopen")
    def test_build_concern_proposal_with_ai_uses_json_schema_and_custom_token_budget(self, mock_urlopen):
        captured_payload: dict[str, object] = {}

        def fake_urlopen(*args, **kwargs):
            http_request = args[0]
            captured_payload.update(json.loads(http_request.data.decode("utf-8")))
            return _FakeHTTPResponse(
                {
                    "status": "completed",
                    "output_text": json.dumps({"summary": "Proposal summary", "changes": []}),
                }
            )

        mock_urlopen.side_effect = fake_urlopen
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")

        result = build_concern_proposal_with_ai(
            {"project": {"slug": self.project.slug}},
            concern,
            [self._section("requirements")],
        )

        self.assertEqual(result.summary, "Proposal summary")
        self.assertEqual(captured_payload["max_output_tokens"], 4321)
        self.assertEqual(captured_payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(captured_payload["text"]["format"]["strict"])

    @patch("specs.concerns._request_openai")
    def test_build_concern_proposal_with_ai_strips_redundant_leading_heading(self, mock_request_openai):
        concern = ProjectConcern.objects.get(project=self.project, fingerprint="human-fallback-ownership")
        requirements = self._section("requirements")
        mock_request_openai.return_value = (
            "gpt-5-mini",
            {
                "summary": "Clarify ownership in requirements.",
                "changes": [
                    {
                        "section_id": requirements["id"],
                        "summary": "Clarify ownership.",
                        "proposed_body": "## Requirements\n\nUpdated requirements body",
                    }
                ],
            },
        )

        result = build_concern_proposal_with_ai(
            {"project": {"slug": self.project.slug}},
            concern,
            [requirements],
        )

        self.assertEqual(result.changes[0]["proposed_body"], "Updated requirements body")

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_DEFAULT_TIMEOUT_SECONDS=None,
        OPENAI_DEFAULT_MAX_INSTRUCTION_CHARS=None,
        OPENAI_DEFAULT_MAX_OUTPUT_TOKENS=None,
        OPENAI_DEFAULT_REASONING_EFFORT=None,
    )
    @patch("specs.openai.request.urlopen")
    def test_request_openai_omits_optional_request_fields_when_settings_are_unset(self, mock_urlopen):
        captured_payload: dict[str, object] = {}

        def fake_urlopen(*args, **kwargs):
            http_request = args[0]
            captured_payload.update(json.loads(http_request.data.decode("utf-8")))
            self.assertNotIn("timeout", kwargs)
            self.assertEqual(len(args), 1)
            return _FakeHTTPResponse(
                {
                    "status": "completed",
                    "output_text": json.dumps({"summary": "ok"}),
                }
            )

        mock_urlopen.side_effect = fake_urlopen

        model, parsed_output = _request_openai(
            schema_name="test_schema",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
            prompt="Return a summary.",
        )

        self.assertEqual(model, "gpt-5-mini")
        self.assertEqual(parsed_output["summary"], "ok")
        self.assertNotIn("max_output_tokens", captured_payload)
        self.assertNotIn("reasoning", captured_payload)

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("specs.openai.request.urlopen")
    def test_run_project_consistency_records_token_usage(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHTTPResponse(
            {
                "id": "resp_consistency",
                "status": "completed",
                "usage": {
                    "input_tokens": 240,
                    "output_tokens": 60,
                    "total_tokens": 300,
                    "input_tokens_details": {"cached_tokens": 40},
                    "output_tokens_details": {"reasoning_tokens": 22},
                },
                "output_text": json.dumps({"issues": []}),
            }
        )

        run = run_project_consistency(self.project, actor=self.project.created_by)

        usage = AIUsageRecord.objects.get(operation="consistency_scan")
        self.assertEqual(usage.project, self.project)
        self.assertEqual(usage.user, self.project.created_by)
        self.assertEqual(usage.consistency_run, run)
        self.assertEqual(usage.input_tokens, 240)
        self.assertEqual(usage.output_tokens, 60)
        self.assertEqual(usage.reasoning_tokens, 22)
        self.assertEqual(usage.cached_input_tokens, 40)
        self.assertEqual(usage.total_tokens, 300)
        self.assertEqual(usage.context_metadata["trigger"], "manual")

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
