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
from projects.models import MembershipRole, Organization, Project, ProjectMembership, ProjectInvite
from specs.models import Assumption, AssumptionStatus, SectionStatus, SpecSection, SpecVersion


def _set_timestamp(instance, when):
    instance.__class__.objects.filter(pk=instance.pk).update(created_at=when, updated_at=when)
    instance.created_at = when
    instance.updated_at = when


def ensure_demo_workspace():
    project = Project.objects.filter(slug="q3-auth-revamp").first()
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
            slug="q3-auth-revamp",
            defaults={
                "organization": org,
                "name": "Authentication Revamp",
                "tagline": "Collaborative, agent-driven spec refinement for a magic-link auth rollout.",
                "summary": (
                    "A strategic shift to remove passwords as the primary authentication method, "
                    "reduce onboarding friction, and keep leadership and engineering aligned."
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
                ProjectMembership(
                    project=project,
                    user=marcus,
                    role=MembershipRole.ENGINEERING,
                    title="Lead Eng",
                ),
                ProjectMembership(project=project, user=lena, role=MembershipRole.PRODUCT, title="Staff PM"),
            ]
        )
        ProjectInvite.objects.get_or_create(
            project=project,
            email="design@example.com",
            defaults={"role": MembershipRole.DESIGN, "invited_by": lena},
        )

    sections = [
        SpecSection.objects.create(
            project=project,
            key="problem-goals",
            title="Problem & Goals",
            summary="Conversion and support issues caused by password friction.",
            body=(
                "Current user onboarding sees a 34% drop-off at the password creation step. "
                "Additionally, support tickets related to password resets account for 20% of our "
                "daily volume.\n\n- Primary Goal: Increase initial signup conversion by 30%.\n"
                "- Secondary Goal: Reduce authentication-related support tickets by 50%."
            ),
            status=SectionStatus.ALIGNED,
            order=1,
        ),
        SpecSection.objects.create(
            project=project,
            key="solution",
            title="Proposed Solution",
            summary="Magic-link-first authentication with SSO retained for enterprise.",
            body=(
                "All new users will authenticate exclusively via email-based magic links.\n\n"
                "Existing passwords will be deprecated with a 30-day grace period. Enterprise "
                "SSO remains fully supported and bypasses magic links entirely.\n\n"
                "If an email takes longer than expected to arrive, users will be prompted to wait "
                "or request a new link."
            ),
            status=SectionStatus.ITERATING,
            order=2,
        ),
        SpecSection.objects.create(
            project=project,
            key="technical-implementation",
            title="Technical Implementation",
            summary="Backend auth flow, rollout strategy, and fallback delivery plan.",
            body=(
                "We need a migration path for existing users, delivery observability, and an "
                "enterprise SSO exception path. Phase 1 remains polling-based for operator-facing "
                "collaboration and approval flows."
            ),
            status=SectionStatus.ITERATING,
            order=3,
        ),
        SpecSection.objects.create(
            project=project,
            key="ux-interfaces",
            title="UX & Interfaces",
            summary="Updated login entry, delayed-email fallback, and admin communication touchpoints.",
            body=(
                "The login UI will simplify to a single email field. If delivery exceeds the "
                "agreed threshold, the UI must expose recovery guidance and retry actions."
            ),
            status=SectionStatus.ITERATING,
            order=4,
        ),
        SpecSection.objects.create(
            project=project,
            key="risks-security",
            title="Risks & Security",
            summary="Unresolved email latency and third-party dependency risks.",
            body=(
                "Email provider latency could increase bounce rates. We also need to confirm "
                "whether payment identity verification is part of Phase 1."
            ),
            status=SectionStatus.BLOCKED,
            order=5,
        ),
    ]

    ceo_post = StreamPost.objects.create(
        project=project,
        author=sarah,
        actor_name="Sarah",
        actor_title="CEO",
        kind=StreamPostKind.COMMENT,
        body=(
            "We need to kill passwords completely for the new platform. Let's move to a magic "
            "link system only. It'll reduce onboarding friction by at least 30%."
        ),
    )
    _set_timestamp(ceo_post, now - timezone.timedelta(hours=1, minutes=8))

    agent_post = StreamPost.objects.create(
        project=project,
        actor_name="Align Agent",
        actor_title="AI Agent",
        kind=StreamPostKind.AGENT,
        body=(
            "Before we lock this in, we need to clarify what happens to existing users and whether "
            "enterprise SSO needs to remain supported."
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
            "Migrating existing users silently to magic links is doable, but we need a grace "
            "period. Enterprise SSO definitely stays for premium orgs."
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
            "What if the email provider delays the magic link? Users will bounce. We need a "
            "fallback if the email takes longer than 10 seconds."
        ),
    )
    _set_timestamp(fallback_post, now - timezone.timedelta(minutes=12))

    fallback_question = OpenQuestion.objects.create(
        project=project,
        title="Fallback for delayed emails?",
        details="Needs technical definition for delivery beyond 10s.",
        severity=IssueSeverity.HIGH,
        status=IssueStatus.OPEN,
        source_post=fallback_post,
        related_section_key="solution",
        raised_by=sarah,
        owner=marcus,
    )

    sso_question = OpenQuestion.objects.create(
        project=project,
        title="What about enterprise SSO?",
        details="Resolved by retaining enterprise SSO for premium orgs.",
        severity=IssueSeverity.MEDIUM,
        status=IssueStatus.RESOLVED,
        source_post=agent_post,
        related_section_key="solution",
        raised_by=sarah,
        owner=marcus,
        resolved_by=marcus,
        resolved_at=now - timezone.timedelta(minutes=42),
    )

    blocker = Blocker.objects.create(
        project=project,
        title="Payment integration timeline dependency",
        details=(
            "Cannot finalize auth flow without confirming if Stripe identity verification will be "
            "required in Phase 1."
        ),
        severity=IssueSeverity.CRITICAL,
        status=IssueStatus.OPEN,
        related_section_key="risks-security",
        raised_by=marcus,
        owner=lena,
    )

    old_decision = Decision.objects.create(
        project=project,
        title="Force migrate everyone immediately",
        summary=(
            "All existing users will have their passwords deleted on launch day and must use magic "
            "links on their next login attempt."
        ),
        status=DecisionStatus.REJECTED,
        proposed_by=sarah,
        related_section_key="solution",
        implementation_progress=0,
    )
    _set_timestamp(old_decision, now - timezone.timedelta(days=1))

    current_decision = Decision.objects.create(
        project=project,
        title="Retain SSO, Migrate Passwords",
        summary=(
            "Magic links become the default for individual users. Existing passwords get a 30-day "
            "grace period and enterprise SSO remains fully supported."
        ),
        status=DecisionStatus.APPROVED,
        proposed_by=sarah,
        source_post=eng_post,
        related_section_key="solution",
        supersedes=old_decision,
        implementation_progress=10,
        approved_at=now - timezone.timedelta(minutes=40),
    )
    _set_timestamp(current_decision, now - timezone.timedelta(minutes=40))
    DecisionApproval.objects.create(decision=current_decision, approver=sarah, approved=True)
    DecisionApproval.objects.create(decision=current_decision, approver=marcus, approved=True)

    implemented_decision = Decision.objects.create(
        project=project,
        title="Use Magic Links as primary auth",
        summary="The default login and signup entry point becomes an email-only magic-link flow.",
        status=DecisionStatus.IMPLEMENTED,
        proposed_by=sarah,
        related_section_key="solution",
        implementation_progress=100,
        approved_at=now - timezone.timedelta(days=12),
        implemented_at=now - timezone.timedelta(days=11),
    )
    _set_timestamp(implemented_decision, now - timezone.timedelta(days=12))

    pending_decision = Decision.objects.create(
        project=project,
        title="Fallback mechanism for delayed Magic Links",
        summary=(
            "If email delivery exceeds 15 seconds, offer a retry flow and define a possible SMS "
            "fallback after approval."
        ),
        status=DecisionStatus.PENDING,
        proposed_by=marcus,
        source_post=fallback_post,
        related_section_key="technical-implementation",
    )
    _set_timestamp(pending_decision, now - timezone.timedelta(minutes=28))

    assumption = Assumption.objects.create(
        project=project,
        section=sections[2],
        title="Enterprise tenants will retain SSO",
        description="Premium organizations require SSO bypass for compliance and DNS-enforced auth.",
        impact="high",
        status=AssumptionStatus.VALIDATED,
        source_post=eng_post,
        created_by=marcus,
        validated_by=sarah,
    )

    open_assumption = Assumption.objects.create(
        project=project,
        section=sections[4],
        title="Email providers can meet a 10 second target",
        description="Current spec assumes delivery latency is acceptable without a second channel.",
        impact="critical",
        status=AssumptionStatus.OPEN,
        source_post=fallback_post,
        created_by=sarah,
    )

    suggestion = AgentSuggestion.objects.create(
        project=project,
        title="Clarify delayed-email fallback",
        summary="The current spec text leaves the >10s fallback too vague for implementation.",
        related_section_key="solution",
        payload={
            "status": SectionStatus.ITERATING,
            "body_append": (
                "Open issue: define the exact UI fallback and operational SLA for delayed email "
                "delivery before implementation starts."
            ),
        },
        source_post=fallback_post,
    )

    snapshots = [
        {
            "title": "Project initialization",
            "summary": "Initial auth direction captured from engineering kick-off.",
            "snapshot": {
                "sections": [
                    {
                        "key": "problem-goals",
                        "title": "Problem & Goals",
                        "summary": sections[0].summary,
                        "body": sections[0].body,
                        "status": SectionStatus.ALIGNED,
                        "order": 1,
                    },
                    {
                        "key": "solution",
                        "title": "Proposed Solution",
                        "summary": "Magic links only, migration strategy still undefined.",
                        "body": "All new users will authenticate exclusively via email-based magic links.",
                        "status": SectionStatus.ITERATING,
                        "order": 2,
                    },
                ]
            },
            "when": now - timezone.timedelta(days=1, hours=2),
            "actor": marcus,
        },
        {
            "title": "Initial magic link proposal",
            "summary": "CEO proposal added, before migration decision.",
            "snapshot": {
                "sections": [
                    {
                        "key": "problem-goals",
                        "title": "Problem & Goals",
                        "summary": sections[0].summary,
                        "body": sections[0].body,
                        "status": SectionStatus.ALIGNED,
                        "order": 1,
                    },
                    {
                        "key": "solution",
                        "title": "Proposed Solution",
                        "summary": sections[1].summary,
                        "body": (
                            "All new users will authenticate exclusively via email-based Magic Links.\n\n"
                            "If an email takes longer than expected to arrive, the system will wait silently "
                            "for delivery to complete."
                        ),
                        "status": SectionStatus.ITERATING,
                        "order": 2,
                    },
                ]
            },
            "when": now - timezone.timedelta(minutes=55),
            "actor": sarah,
        },
        {
            "title": "Agent auto-save",
            "summary": "Decision-linked migration section inserted and fallback wording updated.",
            "snapshot": {
                "sections": [
                    {
                        "key": section.key,
                        "title": section.title,
                        "summary": section.summary,
                        "body": section.body,
                        "status": section.status,
                        "order": section.order,
                    }
                    for section in sections
                ]
            },
            "when": now - timezone.timedelta(minutes=18),
            "actor": None,
        },
    ]

    previous = None
    for number, payload in enumerate(snapshots, start=1):
        version = SpecVersion.objects.create(
            project=project,
            number=number,
            title=payload["title"],
            summary=payload["summary"],
            snapshot=payload["snapshot"],
            created_by=payload["actor"],
            previous_version=previous,
        )
        _set_timestamp(version, payload["when"])
        previous = version

    exports = [
        ExportArtifact.objects.create(
            project=project,
            format=ExportFormat.PRD,
            title="Product Requirements export",
            filename="PRD_AuthRevamp_v2.pdf",
            status=ExportStatus.READY,
            generated_by=marcus,
            share_enabled=True,
            share_token="q3-auth-revamp",
            content="Aligned PRD export",
            configuration={"extension": "pdf"},
        ),
        ExportArtifact.objects.create(
            project=project,
            format=ExportFormat.TASKS,
            title="Task Breakdown export",
            filename="Tasks_AuthRevamp.md",
            status=ExportStatus.READY,
            generated_by=sarah,
            content="Task breakdown export",
            configuration={"extension": "md"},
        ),
        ExportArtifact.objects.create(
            project=project,
            format=ExportFormat.TECH_SPEC,
            title="Technical Spec export",
            filename="TechSpec_Auth_Draft.docx",
            status=ExportStatus.EXPIRED,
            generated_by=marcus,
            expires_at=now - timezone.timedelta(days=2),
            content="Old technical export",
            configuration={"extension": "docx"},
        ),
    ]
    _set_timestamp(exports[0], now - timezone.timedelta(minutes=5))
    _set_timestamp(exports[1], now - timezone.timedelta(days=1))
    _set_timestamp(exports[2], now - timezone.timedelta(days=3))

    return project
