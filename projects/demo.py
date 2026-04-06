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
    DocumentSourceKind,
    DocumentStatus,
    DocumentType,
    ProjectDocument,
    ProjectConcern,
)
from specs.services import bootstrap_documents, capture_document_revision, capture_project_revision

DEMO_PROJECT_SLUG = "q3-auth-revamp"
DEMO_USERNAMES = {"sarah", "marcus", "lena"}


def _set_timestamp(instance, when):
    instance.__class__.objects.filter(pk=instance.pk).update(created_at=when, updated_at=when)
    instance.created_at = when
    instance.updated_at = when


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
                "tagline": "Collaborative, agent-driven refinement for a multi-document auth rollout.",
                "summary": (
                    "A multi-document workspace for shifting from passwords to magic-link-first "
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
            defaults={"role": MembershipRole.DESIGN, "invited_by": lena},
        )

        documents = {document.slug: document for document in bootstrap_documents(project)}
        for index, payload in enumerate(
            (
                {"slug": "goals", "title": "Goals", "document_type": DocumentType.GOALS},
                {"slug": "requirements", "title": "Requirements", "document_type": DocumentType.REQUIREMENTS},
                {"slug": "ui-ux", "title": "UI/UX", "document_type": DocumentType.UI_UX},
                {"slug": "tech-stack", "title": "Tech Stack", "document_type": DocumentType.TECH_STACK},
                {"slug": "infra", "title": "Infra", "document_type": DocumentType.INFRA},
                {
                    "slug": "risks-open-questions",
                    "title": "Risks & Open Questions",
                    "document_type": DocumentType.RISKS_OPEN_QUESTIONS,
                },
            ),
            start=2,
        ):
            document = ProjectDocument.objects.create(
                project=project,
                slug=payload["slug"],
                title=payload["title"],
                document_type=payload["document_type"],
                source_kind=DocumentSourceKind.PRESET,
                body="",
                status=DocumentStatus.ITERATING,
                order=index,
                is_required=False,
            )
            documents[document.slug] = document

        seed_content = {
            "overview": {
                "body": (
                    "Authentication is moving to a multi-document planning model so product, design, "
                    "and engineering can maintain separate source documents while still tracking alignment."
                ),
                "status": DocumentStatus.ALIGNED,
            },
            "goals": {
                "body": (
                    "- Increase signup conversion by 30%.\n"
                    "- Reduce password-reset support load by 50%.\n"
                    "- Keep enterprise SSO as a compliant escape hatch."
                ),
                "status": DocumentStatus.ALIGNED,
            },
            "requirements": {
                "body": (
                    "- New individual users authenticate with magic links.\n"
                    "- Existing password users get a 30-day grace period.\n"
                    "- Enterprise tenants retain SSO."
                ),
                "status": DocumentStatus.ITERATING,
            },
            "ui-ux": {
                "body": (
                    "The login and signup entry points collapse to a single email field. "
                    "Delayed delivery needs visible recovery guidance and a retry affordance."
                ),
                "status": DocumentStatus.ITERATING,
            },
            "tech-stack": {
                "body": (
                    "Auth services need token issuance, delivery telemetry, and a reversible rollout path "
                    "for password deprecation."
                ),
                "status": DocumentStatus.ITERATING,
            },
            "infra": {
                "body": (
                    "Infra needs provider health monitoring, retry-safe delivery pipelines, and tenant-aware "
                    "SSO routing."
                ),
                "status": DocumentStatus.ITERATING,
            },
            "risks-open-questions": {
                "body": (
                    "- Email latency beyond 10s may cause drop-off.\n"
                    "- Phase 1 payment identity requirements remain unconfirmed."
                ),
                "status": DocumentStatus.BLOCKED,
            },
        }

        initial_revision = capture_project_revision(
            project=project,
            title="Workspace migrated to multi-document model",
            summary="Created the expanded starter document set for the auth initiative.",
            actor=marcus,
        )
        for slug, payload in seed_content.items():
            document = documents[slug]
            document.body = payload["body"]
            document.status = payload["status"]
            document.save(update_fields=["body", "status", "updated_at"])
            capture_document_revision(
                document=document,
                title=f"Seeded {document.title}",
                summary=document.body[:160],
                actor=marcus,
                project_revision=initial_revision,
            )

        follow_up_revision = capture_project_revision(
            project=project,
            title="Infra and UI/UX refined",
            summary="Refined fallback and delivery visibility expectations across docs.",
            actor=lena,
        )
        documents["infra"].body += "\n\nDelivery health must be exposed in operator tooling every 5 minutes."
        documents["infra"].save(update_fields=["body", "updated_at"])
        capture_document_revision(
            document=documents["infra"],
            title="Infra refinement",
            summary=documents["infra"].body[:160],
            actor=lena,
            project_revision=follow_up_revision,
        )
        documents["ui-ux"].body += "\n\nIf delivery exceeds the SLA, the UI must explain next steps in plain language."
        documents["ui-ux"].save(update_fields=["body", "updated_at"])
        capture_document_revision(
            document=documents["ui-ux"],
            title="UI/UX refinement",
            summary=documents["ui-ux"].body[:160],
            actor=lena,
            project_revision=follow_up_revision,
        )

        ceo_post = StreamPost.objects.create(
            project=project,
            author=sarah,
            actor_name="Sarah",
            actor_title="CEO",
            kind=StreamPostKind.COMMENT,
            body=(
                "We need each core planning area in its own document now. I still want magic links to be "
                "the primary direction, but contradictions across docs must be visible."
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
                "document set."
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
                "If the delivery provider slips, the experience degrades quickly. I want the project documents "
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

        fallback_concern = ProjectConcern.objects.create(
            project=project,
            run=concern_run,
            source_post=agent_post,
            fingerprint="fallback-mismatch",
            concern_type=ConcernType.CONSISTENCY,
            raised_by_kind=ConcernRaisedByKind.AI,
            title="Fallback mismatch across requirements, UI/UX, and infra",
            summary="The delayed-email fallback still differs across the product, UX, and infra documents.",
            severity=ConcernSeverity.HIGH,
            status=ConcernStatus.OPEN,
            source_refs=[
                {"kind": "document", "identifier": "requirements", "label": "Requirements"},
                {"kind": "document", "identifier": "ui-ux", "label": "UI/UX"},
                {"kind": "document", "identifier": "infra", "label": "Infra"},
            ],
            recommendation="Define one shared fallback contract and keep the affected documents in sync.",
            detected_at=now - timezone.timedelta(minutes=4),
            last_seen_at=now - timezone.timedelta(minutes=4),
            last_reevaluated_at=now - timezone.timedelta(minutes=4),
        )
        fallback_concern.documents.add(documents["requirements"], documents["ui-ux"], documents["infra"])

        viability_concern = ProjectConcern.objects.create(
            project=project,
            run=concern_run,
            source_post=fallback_post,
            fingerprint="phase-one-identity-scope",
            concern_type=ConcernType.BUSINESS_VIABILITY,
            raised_by_kind=ConcernRaisedByKind.AI,
            title="Phase 1 identity scope is still commercially ambiguous",
            summary="The current project documents still do not make it clear whether identity verification joins Phase 1.",
            severity=ConcernSeverity.MEDIUM,
            status=ConcernStatus.OPEN,
            source_refs=[
                {"kind": "document", "identifier": "risks-open-questions", "label": "Risks & Open Questions"},
                {"kind": "document", "identifier": "overview", "label": "Overview"},
            ],
            recommendation="Confirm the Phase 1 commercial scope and reflect it in the project overview and risks document.",
            detected_at=now - timezone.timedelta(minutes=4),
            last_seen_at=now - timezone.timedelta(minutes=4),
            last_reevaluated_at=now - timezone.timedelta(minutes=4),
        )
        viability_concern.documents.add(documents["overview"], documents["risks-open-questions"])

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
                {"kind": "document", "identifier": "requirements", "label": "Requirements"},
                {"kind": "document", "identifier": "infra", "label": "Infra"},
            ],
            recommendation="Assign one owner, update the documents, and then re-evaluate this concern.",
            detected_at=eng_post.created_at,
            last_seen_at=eng_post.created_at,
            reevaluation_requested_at=now - timezone.timedelta(minutes=10),
            created_by=marcus,
        )
        human_concern.documents.add(documents["requirements"], documents["infra"])

        concern_post = StreamPost.objects.create(
            project=project,
            author=marcus,
            actor_name="Marcus",
            actor_title="Lead Eng",
            kind=StreamPostKind.COMMENT,
            concern=fallback_concern,
            body="We need the same SLA and same operator playbook spelled out in all three docs.",
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
            document=documents["requirements"],
            summary="Add one explicit fallback flow and SLA to the product requirement.",
            original_body=documents["requirements"].body,
            proposed_body=(
                f"{documents['requirements'].body}\n"
                "- If delivery exceeds 15 seconds, the UI shows retry guidance and a support escalation path.\n"
                "- The same 15 second threshold becomes the shared fallback contract across product and infra.\n"
            ),
        )
        ConcernProposalChange.objects.create(
            proposal=fallback_proposal,
            document=documents["infra"],
            summary="Mirror the same fallback contract in operator-facing infra notes.",
            original_body=documents["infra"].body,
            proposed_body=(
                f"{documents['infra'].body}\n\n"
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
            related_document=documents["requirements"],
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
            related_document=documents["requirements"],
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
            related_document=documents["risks-open-questions"],
            raised_by=marcus,
            owner=lena,
        )

        old_decision = Decision.objects.create(
            project=project,
            title="Force migrate everyone immediately",
            summary="Delete all passwords on launch day and require magic links instantly.",
            status=DecisionStatus.REJECTED,
            proposed_by=sarah,
            related_document=documents["requirements"],
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
            related_document=documents["requirements"],
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
            related_document=documents["requirements"],
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
            related_document=documents["infra"],
        )

        Assumption.objects.create(
            project=project,
            document=documents["requirements"],
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
            document=documents["risks-open-questions"],
            title="Email providers can meet a 10 second target",
            description="The current document set assumes delivery latency is acceptable without a second channel.",
            impact="critical",
            status=AssumptionStatus.OPEN,
            source_post=fallback_post,
            created_by=sarah,
        )

        AgentSuggestion.objects.create(
            project=project,
            title="Clarify delayed-email fallback",
            summary="The current document set leaves the delayed-email fallback too vague for implementation.",
            related_document=documents["requirements"],
            payload={
                "status": DocumentStatus.ITERATING,
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
                {"kind": "document", "identifier": "requirements", "label": "Requirements"},
                {"kind": "document", "identifier": "infra", "label": "Infra"},
            ],
            recommendation="Define the same delayed-email fallback contract in both documents.",
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
            configuration={"document_slugs": "overview,goals,requirements,ui-ux,tech-stack,infra,risks-open-questions"},
            content="# Authentication Revamp\n\nSeed export.",
            share_enabled=True,
            share_token="demo-share-token",
        )

    return project
