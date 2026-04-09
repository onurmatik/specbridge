from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from agents.models import AgentSuggestion
from alignment.models import (
    Blocker,
    Decision,
    DecisionApproval,
    DecisionStatus,
    IssueSeverity,
    IssueStatus,
    OpenQuestion,
    StreamPost,
    StreamPostKind,
)
from exports.models import ExportArtifact, ExportFormat, ExportStatus
from projects.models import MembershipRole, Organization, Project, ProjectInvite, ProjectMembership
from specs.models import (
    Assumption,
    AssumptionStatus,
    ConcernProposal,
    ConcernProposalChange,
    ConcernProposalStatus,
    ConcernRaisedByKind,
    ConcernRun,
    ConcernRunStatus,
    ConcernSeverity,
    ConcernStatus,
    ConcernType,
    ConsistencyIssue,
    ConsistencyIssueSeverity,
    ConsistencyIssueStatus,
    ConsistencyRun,
    ConsistencyRunStatus,
    ProjectConcern,
)
from specs.services import bootstrap_spec_document, capture_project_revision, ensure_spec_document, section_summaries
from specs.spec_document import markdown_to_blocks, update_section_content

DEMO_PROJECT_SLUG = "q3-auth-revamp"
DEMO_USERNAMES = {"sarah", "marcus", "lena"}


def _set_timestamp(instance, when):
    instance.__class__.objects.filter(pk=instance.pk).update(created_at=when, updated_at=when)
    instance.created_at = when
    instance.updated_at = when


def _section_lookup(project):
    return {section["key"]: section for section in section_summaries(project)}


def _apply_section_bodies(project, payloads: dict[str, dict]):
    spec_document = ensure_spec_document(project)
    content_json = spec_document.content_json
    lookup = _section_lookup(project)
    for key, payload in payloads.items():
        section = lookup[key]
        content_json, _, _ = update_section_content(
            content_json,
            section["id"],
            title=payload.get("title"),
            status=payload.get("status"),
            content_blocks=markdown_to_blocks(payload.get("body", "")),
        )
    spec_document.content_json = content_json
    spec_document.save(update_fields=["content_json", "updated_at"])
    return _section_lookup(project)


def ensure_demo_workspace():
    project = Project.objects.filter(slug=DEMO_PROJECT_SLUG).first()
    if project:
        return project

    now = timezone.now()
    with transaction.atomic():
        org, _ = Organization.objects.get_or_create(
            slug="align-labs",
            defaults={"name": "Align Labs"},
        )

        sarah, created = User.objects.get_or_create(
            username="sarah",
            defaults={
                "email": "sarah@example.com",
                "first_name": "Sarah",
                "last_name": "Stone",
                "title": "CEO",
                "avatar_seed": "CEO",
            },
        )
        if created:
            sarah.set_password("specbridge")
            sarah.save()

        marcus, created = User.objects.get_or_create(
            username="marcus",
            defaults={
                "email": "marcus@example.com",
                "first_name": "Marcus",
                "last_name": "Cole",
                "title": "Lead Eng",
                "avatar_seed": "Marcus",
            },
        )
        if created:
            marcus.set_password("specbridge")
            marcus.save()

        lena, created = User.objects.get_or_create(
            username="lena",
            defaults={
                "email": "lena@example.com",
                "first_name": "Lena",
                "last_name": "Park",
                "title": "Staff PM",
                "avatar_seed": "Lena",
            },
        )
        if created:
            lena.set_password("specbridge")
            lena.save()

        project, project_created = Project.objects.get_or_create(
            slug=DEMO_PROJECT_SLUG,
            defaults={
                "organization": org,
                "name": "Authentication Revamp",
                "tagline": "Collaborative, agent-driven refinement for a single-spec auth rollout.",
                "summary": (
                    "A single-spec workspace for shifting from passwords to magic-link-first "
                    "authentication while keeping product, design, and engineering aligned."
                ),
                "status_label": "Aligning",
                "created_by": sarah,
                "last_activity_at": now,
            },
        )
        if not project_created:
            return project

        ProjectMembership.objects.bulk_create(
            [
                ProjectMembership(project=project, user=sarah, role=MembershipRole.CEO, title="CEO"),
                ProjectMembership(project=project, user=marcus, role=MembershipRole.ENGINEERING, title="Lead Eng"),
                ProjectMembership(project=project, user=lena, role=MembershipRole.PRODUCT, title="Staff PM"),
            ]
        )
        ProjectInvite.objects.get_or_create(
            project=project,
            email="design@example.com",
            defaults={"role": MembershipRole.DESIGN, "invited_by": lena, "last_sent_at": now},
        )

        bootstrap_spec_document(project)
        sections = _apply_section_bodies(
            project,
            {
                "overview": {
                    "body": (
                        "Authentication is moving to a single spec workspace so product, design, "
                        "and engineering can maintain one structured source of truth while still tracking alignment."
                    ),
                    "status": "aligned",
                },
                "goals": {
                    "body": (
                        "- Increase signup conversion by 30%.\n"
                        "- Reduce password-reset support load by 50%.\n"
                        "- Keep enterprise SSO as a compliant escape hatch."
                    ),
                    "status": "aligned",
                },
                "requirements": {
                    "body": (
                        "- New individual users authenticate with magic links.\n"
                        "- Existing password users get a 30-day grace period.\n"
                        "- Enterprise tenants retain SSO."
                    ),
                    "status": "iterating",
                },
                "ui-ux": {
                    "body": (
                        "The login and signup entry points collapse to a single email field. "
                        "Delayed delivery needs visible recovery guidance and a retry affordance."
                    ),
                    "status": "iterating",
                },
                "tech-stack": {
                    "body": (
                        "Auth services need token issuance, delivery telemetry, and a reversible rollout path "
                        "for password deprecation."
                    ),
                    "status": "iterating",
                },
                "infra": {
                    "body": (
                        "Infra needs provider health monitoring, retry-safe delivery pipelines, and tenant-aware "
                        "SSO routing."
                    ),
                    "status": "iterating",
                },
                "risks-open-questions": {
                    "body": (
                        "- Email latency beyond 10s may cause drop-off.\n"
                        "- Phase 1 payment identity requirements remain unconfirmed."
                    ),
                    "status": "blocked",
                },
            },
        )
        capture_project_revision(
            project=project,
            title="Workspace migrated to single spec model",
            summary="Created the expanded starter section set for the auth initiative.",
            actor=marcus,
        )

        sections = _apply_section_bodies(
            project,
            {
                "infra": {
                    "body": (
                        "Infra needs provider health monitoring, retry-safe delivery pipelines, and tenant-aware "
                        "SSO routing.\n\n"
                        "Delivery health must be exposed in operator tooling every 5 minutes."
                    ),
                    "status": "iterating",
                },
                "ui-ux": {
                    "body": (
                        "The login and signup entry points collapse to a single email field. "
                        "Delayed delivery needs visible recovery guidance and a retry affordance.\n\n"
                        "If delivery exceeds the SLA, the UI must explain next steps in plain language."
                    ),
                    "status": "iterating",
                },
            },
        )
        capture_project_revision(
            project=project,
            title="Infra and UI/UX refined",
            summary="Refined fallback and delivery visibility expectations across sections.",
            actor=lena,
        )

        ceo_post = StreamPost.objects.create(
            project=project,
            author=sarah,
            actor_name="Sarah",
            actor_title="CEO",
            kind=StreamPostKind.COMMENT,
            body=(
                "We need each core planning area in one shared spec now. I still want magic links to be "
                "the primary direction, but contradictions across sections must be visible."
            ),
        )
        _set_timestamp(ceo_post, now - timezone.timedelta(hours=1, minutes=8))

        agent_post = StreamPost.objects.create(
            project=project,
            actor_name="Align Agent",
            actor_title="AI Agent",
            kind=StreamPostKind.AGENT,
            body=(
                "Requirements and infra are close, but the fallback path is still underspecified across the "
                "spec."
            ),
        )
        _set_timestamp(agent_post, now - timezone.timedelta(hours=1, minutes=2))

        eng_post = StreamPost.objects.create(
            project=project,
            author=marcus,
            actor_name="Marcus",
            actor_title="Lead Eng",
            kind=StreamPostKind.COMMENT,
            body=(
                "We can keep enterprise SSO, but delayed-email fallback must be consistent between requirements, "
                "UI/UX, and infra."
            ),
        )
        _set_timestamp(eng_post, now - timezone.timedelta(minutes=45))

        fallback_post = StreamPost.objects.create(
            project=project,
            author=sarah,
            actor_name="Sarah",
            actor_title="CEO",
            kind=StreamPostKind.COMMENT,
            body=(
                "If the delivery provider slips, the experience degrades quickly. I want the spec "
                "to spell out the recovery path."
            ),
        )
        _set_timestamp(fallback_post, now - timezone.timedelta(minutes=12))

        concern_run = ConcernRun.objects.create(
            project=project,
            provider="openai",
            model="gpt-5-mini",
            status=ConcernRunStatus.COMPLETED,
            concern_count=3,
            scopes=[
                ConcernType.CONSISTENCY,
                ConcernType.IMPLEMENTABILITY,
                ConcernType.BUSINESS_VIABILITY,
            ],
            analyzed_at=now - timezone.timedelta(minutes=4),
        )

        fallback_refs = [sections["requirements"], sections["ui-ux"], sections["infra"]]
        fallback_concern = ProjectConcern.objects.create(
            project=project,
            run=concern_run,
            source_post=agent_post,
            fingerprint="fallback-mismatch",
            concern_type=ConcernType.CONSISTENCY,
            raised_by_kind=ConcernRaisedByKind.AI,
            title="Fallback mismatch across requirements, UI/UX, and infra",
            summary="The delayed-email fallback still differs across the product, UX, and infra sections.",
            severity=ConcernSeverity.HIGH,
            status=ConcernStatus.OPEN,
            source_refs=[
                {"kind": "section", "identifier": section["id"], "label": section["title"]}
                for section in fallback_refs
            ],
            node_refs=[
                {
                    "section_id": section["id"],
                    "node_id": "",
                    "label": section["title"],
                    "excerpt": section["body"][:240],
                }
                for section in fallback_refs
            ],
            recommendation="Define one shared fallback contract and keep the affected sections in sync.",
            detected_at=now - timezone.timedelta(minutes=4),
            last_seen_at=now - timezone.timedelta(minutes=4),
            last_reevaluated_at=now - timezone.timedelta(minutes=4),
        )

        viability_refs = [sections["overview"], sections["risks-open-questions"]]
        viability_concern = ProjectConcern.objects.create(
            project=project,
            run=concern_run,
            source_post=fallback_post,
            fingerprint="phase-one-identity-scope",
            concern_type=ConcernType.BUSINESS_VIABILITY,
            raised_by_kind=ConcernRaisedByKind.AI,
            title="Phase 1 identity scope is still commercially ambiguous",
            summary="The current spec still does not make it clear whether identity verification joins Phase 1.",
            severity=ConcernSeverity.MEDIUM,
            status=ConcernStatus.OPEN,
            source_refs=[
                {"kind": "section", "identifier": section["id"], "label": section["title"]}
                for section in viability_refs
            ],
            node_refs=[
                {
                    "section_id": section["id"],
                    "node_id": "",
                    "label": section["title"],
                    "excerpt": section["body"][:240],
                }
                for section in viability_refs
            ],
            recommendation="Confirm the Phase 1 commercial scope and reflect it in the overview and risks sections.",
            detected_at=now - timezone.timedelta(minutes=4),
            last_seen_at=now - timezone.timedelta(minutes=4),
            last_reevaluated_at=now - timezone.timedelta(minutes=4),
        )

        human_refs = [sections["requirements"], sections["infra"]]
        human_concern = ProjectConcern.objects.create(
            project=project,
            source_post=eng_post,
            fingerprint="human-fallback-ownership",
            concern_type=ConcernType.HUMAN_FLAG,
            raised_by_kind=ConcernRaisedByKind.HUMAN,
            title="Need one owner for delayed-email recovery",
            summary="The team still needs clear ownership for the fallback contract before implementation starts.",
            severity=ConcernSeverity.MEDIUM,
            status=ConcernStatus.STALE,
            source_refs=[
                {"kind": "stream_post", "identifier": str(eng_post.id), "label": "Marcus comment"},
                *[
                    {"kind": "section", "identifier": section["id"], "label": section["title"]}
                    for section in human_refs
                ],
            ],
            node_refs=[
                {
                    "section_id": section["id"],
                    "node_id": "",
                    "label": section["title"],
                    "excerpt": section["body"][:240],
                }
                for section in human_refs
            ],
            recommendation="Assign one owner, update the sections, and then re-evaluate this concern.",
            detected_at=eng_post.created_at,
            last_seen_at=eng_post.created_at,
            reevaluation_requested_at=now - timezone.timedelta(minutes=10),
            created_by=marcus,
        )

        concern_post = StreamPost.objects.create(
            project=project,
            author=marcus,
            actor_name="Marcus",
            actor_title="Lead Eng",
            kind=StreamPostKind.COMMENT,
            concern=fallback_concern,
            body="We need the same SLA and same operator playbook spelled out in all three sections.",
        )
        _set_timestamp(concern_post, now - timezone.timedelta(minutes=7))

        agent_concern_post = StreamPost.objects.create(
            project=project,
            actor_name="Align Agent",
            actor_title="AI Agent",
            kind=StreamPostKind.AGENT,
            concern=fallback_concern,
            body="I can generate a coordinated patch across requirements and infra once the team agrees on the fallback contract.",
        )
        _set_timestamp(agent_concern_post, now - timezone.timedelta(minutes=5))

        fallback_proposal = ConcernProposal.objects.create(
            project=project,
            concern=fallback_concern,
            provider="openai",
            model="gpt-5-mini",
            summary="Normalize the delayed-email fallback between requirements and infra.",
            status=ConcernProposalStatus.OPEN,
            requested_by=lena,
        )
        ConcernProposalChange.objects.create(
            proposal=fallback_proposal,
            section_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            section_id=sections["requirements"]["id"],
            section_title=sections["requirements"]["title"],
            original_section_json={},
            proposed_section_json={
                "type": "specSection",
                "attrs": {
                    "id": sections["requirements"]["id"],
                    "key": sections["requirements"]["key"],
                    "title": sections["requirements"]["title"],
                    "kind": sections["requirements"]["kind"],
                    "status": sections["requirements"]["status"],
                    "required": sections["requirements"]["required"],
                    "legacy_slug": sections["requirements"]["legacy_slug"],
                },
                "content": markdown_to_blocks(
                    f"{sections['requirements']['body']}\n"
                    "- If delivery exceeds 15 seconds, the UI shows retry guidance and a support escalation path.\n"
                    "- The same 15 second threshold becomes the shared fallback contract across product and infra.\n"
                ),
            },
            summary="Add one explicit fallback flow and SLA to the product requirement.",
            original_body=sections["requirements"]["body"],
            proposed_body=(
                f"{sections['requirements']['body']}\n"
                "- If delivery exceeds 15 seconds, the UI shows retry guidance and a support escalation path.\n"
                "- The same 15 second threshold becomes the shared fallback contract across product and infra.\n"
            ),
        )
        ConcernProposalChange.objects.create(
            proposal=fallback_proposal,
            section_ref={
                "section_id": sections["infra"]["id"],
                "node_id": "",
                "label": sections["infra"]["title"],
                "excerpt": sections["infra"]["body"][:240],
            },
            section_id=sections["infra"]["id"],
            section_title=sections["infra"]["title"],
            original_section_json={},
            proposed_section_json={
                "type": "specSection",
                "attrs": {
                    "id": sections["infra"]["id"],
                    "key": sections["infra"]["key"],
                    "title": sections["infra"]["title"],
                    "kind": sections["infra"]["kind"],
                    "status": sections["infra"]["status"],
                    "required": sections["infra"]["required"],
                    "legacy_slug": sections["infra"]["legacy_slug"],
                },
                "content": markdown_to_blocks(
                    f"{sections['infra']['body']}\n\n"
                    "Delayed email recovery uses the same 15 second SLA as product. Operator tooling must show when that SLA is breached and what escalation path is active."
                ),
            },
            summary="Mirror the same fallback contract in operator-facing infra notes.",
            original_body=sections["infra"]["body"],
            proposed_body=(
                f"{sections['infra']['body']}\n\n"
                "Delayed email recovery uses the same 15 second SLA as product. Operator tooling must show when that SLA is breached and what escalation path is active."
            ),
        )

        OpenQuestion.objects.create(
            project=project,
            title="Fallback for delayed emails?",
            details="Requirements and UI/UX need a tighter definition for delivery beyond 10s.",
            severity=IssueSeverity.HIGH,
            status=IssueStatus.OPEN,
            source_post=fallback_post,
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            raised_by=sarah,
            owner=marcus,
        )

        OpenQuestion.objects.create(
            project=project,
            title="What about enterprise SSO?",
            details="Resolved by retaining enterprise SSO for premium orgs.",
            severity=IssueSeverity.MEDIUM,
            status=IssueStatus.RESOLVED,
            source_post=agent_post,
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            raised_by=sarah,
            owner=marcus,
            resolved_by=marcus,
            resolved_at=now - timezone.timedelta(minutes=42),
        )

        Blocker.objects.create(
            project=project,
            title="Payment integration timeline dependency",
            details="Cannot finalize auth rollout without confirming whether identity verification joins Phase 1.",
            severity=IssueSeverity.CRITICAL,
            status=IssueStatus.OPEN,
            primary_ref={
                "section_id": sections["risks-open-questions"]["id"],
                "node_id": "",
                "label": sections["risks-open-questions"]["title"],
                "excerpt": sections["risks-open-questions"]["body"][:240],
            },
            raised_by=marcus,
            owner=lena,
        )

        old_decision = Decision.objects.create(
            project=project,
            title="Force migrate everyone immediately",
            summary="Delete all passwords on launch day and require magic links instantly.",
            status=DecisionStatus.REJECTED,
            proposed_by=sarah,
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            implementation_progress=0,
        )
        _set_timestamp(old_decision, now - timezone.timedelta(days=1))

        current_decision = Decision.objects.create(
            project=project,
            title="Retain SSO, Migrate Passwords",
            summary=(
                "Magic links become default for individuals. Existing passwords get a 30-day grace period "
                "and enterprise SSO remains fully supported."
            ),
            status=DecisionStatus.APPROVED,
            proposed_by=sarah,
            source_post=eng_post,
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            supersedes=old_decision,
            implementation_progress=10,
            approved_at=now - timezone.timedelta(minutes=40),
        )
        _set_timestamp(current_decision, now - timezone.timedelta(minutes=40))
        DecisionApproval.objects.create(decision=current_decision, approver=sarah, approved=True)
        DecisionApproval.objects.create(decision=current_decision, approver=marcus, approved=True)

        Decision.objects.create(
            project=project,
            title="Use Magic Links as primary auth",
            summary="The default login and signup entry point becomes an email-only magic-link flow.",
            status=DecisionStatus.IMPLEMENTED,
            proposed_by=sarah,
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            implementation_progress=100,
            approved_at=now - timezone.timedelta(days=12),
            implemented_at=now - timezone.timedelta(days=11),
        )

        Decision.objects.create(
            project=project,
            title="Fallback mechanism for delayed Magic Links",
            summary="If email delivery exceeds 15 seconds, offer retry guidance and define an escalation path.",
            status=DecisionStatus.PENDING,
            proposed_by=marcus,
            source_post=fallback_post,
            primary_ref={
                "section_id": sections["infra"]["id"],
                "node_id": "",
                "label": sections["infra"]["title"],
                "excerpt": sections["infra"]["body"][:240],
            },
        )

        Assumption.objects.create(
            project=project,
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            title="Enterprise tenants will retain SSO",
            description="Premium organizations require SSO bypass for compliance and DNS-enforced auth.",
            impact="high",
            status=AssumptionStatus.VALIDATED,
            source_post=eng_post,
            created_by=marcus,
            validated_by=sarah,
        )

        Assumption.objects.create(
            project=project,
            primary_ref={
                "section_id": sections["risks-open-questions"]["id"],
                "node_id": "",
                "label": sections["risks-open-questions"]["title"],
                "excerpt": sections["risks-open-questions"]["body"][:240],
            },
            title="Email providers can meet a 10 second target",
            description="The current spec assumes delivery latency is acceptable without a second channel.",
            impact="critical",
            status=AssumptionStatus.OPEN,
            source_post=fallback_post,
            created_by=sarah,
        )

        AgentSuggestion.objects.create(
            project=project,
            title="Clarify delayed-email fallback",
            summary="The current spec leaves the delayed-email fallback too vague for implementation.",
            primary_ref={
                "section_id": sections["requirements"]["id"],
                "node_id": "",
                "label": sections["requirements"]["title"],
                "excerpt": sections["requirements"]["body"][:240],
            },
            payload={
                "status": "iterating",
                "body_append": (
                    "Open issue: define the exact UI fallback and operational SLA for delayed email delivery "
                    "before implementation starts."
                ),
            },
            source_post=fallback_post,
        )

        consistency_run = ConsistencyRun.objects.create(
            project=project,
            provider="openai",
            model="gpt-5-mini",
            status=ConsistencyRunStatus.COMPLETED,
            issue_count=1,
            analyzed_at=now - timezone.timedelta(minutes=5),
        )
        ConsistencyIssue.objects.create(
            project=project,
            run=consistency_run,
            fingerprint="fallback-mismatch",
            title="Fallback mismatch across requirements and infra",
            summary="Requirements mention a retry path but infra does not define the recovery mechanism or SLA source.",
            severity=ConsistencyIssueSeverity.HIGH,
            status=ConsistencyIssueStatus.OPEN,
            source_refs=[
                {"kind": "section", "identifier": sections["requirements"]["id"], "label": sections["requirements"]["title"]},
                {"kind": "section", "identifier": sections["infra"]["id"], "label": sections["infra"]["title"]},
            ],
            recommendation="Define the same delayed-email fallback contract in both sections.",
            detected_at=now - timezone.timedelta(minutes=5),
            last_seen_at=now - timezone.timedelta(minutes=5),
        )

        ExportArtifact.objects.create(
            project=project,
            format=ExportFormat.PRD,
            title="Product Requirements export",
            filename="q3-auth-revamp_prd_seed.md",
            status=ExportStatus.READY,
            generated_by=sarah,
            configuration={
                "section_ids": ",".join(section["id"] for section in sections.values()),
                "file_type": "md",
            },
            content="# Authentication Revamp\n\nSeed export.",
            share_enabled=True,
            share_token="demo-share-token",
        )

    return project
