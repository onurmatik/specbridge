from django.conf import settings
from django.db import models
from django.utils import timezone

from specbridge.model_mixins import TimeStampedModel


class DocumentStatus(models.TextChoices):
    ALIGNED = "aligned", "Aligned"
    ITERATING = "iterating", "Iterating"
    BLOCKED = "blocked", "Blocked"


class DocumentType(models.TextChoices):
    OVERVIEW = "overview", "Overview"
    GOALS = "goals", "Goals"
    REQUIREMENTS = "requirements", "Requirements"
    UI_UX = "ui-ux", "UI/UX"
    TECH_STACK = "tech-stack", "Tech Stack"
    INFRA = "infra", "Infra"
    RISKS_OPEN_QUESTIONS = "risks-open-questions", "Risks & Open Questions"
    CUSTOM = "custom", "Custom"


class AssumptionStatus(models.TextChoices):
    OPEN = "open", "Open"
    VALIDATED = "validated", "Validated"
    INVALIDATED = "invalidated", "Invalidated"


class AuditEventType(models.TextChoices):
    PROJECT_REVISION_CREATED = "project_revision_created", "Project Revision Created"
    DOCUMENT_CREATED = "document_created", "Document Created"
    DOCUMENT_UPDATED = "document_updated", "Document Updated"
    DOCUMENT_DELETED = "document_deleted", "Document Deleted"
    DOCUMENT_REORDERED = "document_reordered", "Document Reordered"
    DECISION_APPROVED = "decision_approved", "Decision Approved"
    DECISION_REJECTED = "decision_rejected", "Decision Rejected"
    DECISION_IMPLEMENTED = "decision_implemented", "Decision Implemented"
    ASSUMPTION_CREATED = "assumption_created", "Assumption Created"
    ASSUMPTION_VALIDATED = "assumption_validated", "Assumption Validated"
    ASSUMPTION_INVALIDATED = "assumption_invalidated", "Assumption Invalidated"
    AGENT_APPLIED = "agent_applied", "Agent Applied"
    AGENT_DISMISSED = "agent_dismissed", "Agent Dismissed"
    CONCERN_RUN_COMPLETED = "concern_run_completed", "Concern Run Completed"
    CONCERN_RUN_FAILED = "concern_run_failed", "Concern Run Failed"
    CONCERN_PROMOTED = "concern_promoted", "Concern Promoted"
    CONCERN_DISMISSED = "concern_dismissed", "Concern Dismissed"
    CONCERN_REEVALUATED = "concern_reevaluated", "Concern Re-Evaluated"
    CONCERN_MARKED_STALE = "concern_marked_stale", "Concern Marked Stale"
    CONCERN_PROPOSAL_CREATED = "concern_proposal_created", "Concern Proposal Created"
    CONCERN_PROPOSAL_CHANGE_ACCEPTED = "concern_proposal_change_accepted", "Concern Proposal Change Accepted"
    CONCERN_PROPOSAL_CHANGE_REJECTED = "concern_proposal_change_rejected", "Concern Proposal Change Rejected"
    CONSISTENCY_RUN_COMPLETED = "consistency_run_completed", "Consistency Run Completed"
    CONSISTENCY_RUN_FAILED = "consistency_run_failed", "Consistency Run Failed"
    CONSISTENCY_ISSUE_RESOLVED = "consistency_issue_resolved", "Consistency Issue Resolved"
    CONSISTENCY_ISSUE_DISMISSED = "consistency_issue_dismissed", "Consistency Issue Dismissed"
    EXPORT_CREATED = "export_created", "Export Created"
    MEMBERSHIP_CHANGED = "membership_changed", "Membership Changed"


class ConcernType(models.TextChoices):
    CONSISTENCY = "consistency", "Consistency"
    IMPLEMENTABILITY = "implementability", "Implementability"
    USABILITY = "usability", "Usability"
    BUSINESS_VIABILITY = "business_viability", "Business Viability"
    HUMAN_FLAG = "human_flag", "Human Flag"


class ConcernRaisedByKind(models.TextChoices):
    AI = "ai", "AI"
    HUMAN = "human", "Human"
    SYSTEM = "system", "System"


class ConcernStatus(models.TextChoices):
    OPEN = "open", "Open"
    STALE = "stale", "Stale"
    RESOLVED = "resolved", "Resolved"
    DISMISSED = "dismissed", "Dismissed"


class ConcernRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ConcernSeverity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class ConcernProposalStatus(models.TextChoices):
    OPEN = "open", "Open"
    PARTIALLY_APPLIED = "partially_applied", "Partially Applied"
    COMPLETED = "completed", "Completed"
    REJECTED = "rejected", "Rejected"


class ConcernProposalChangeStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


class ConsistencyRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ConsistencyIssueSeverity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class ConsistencyIssueStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"
    DISMISSED = "dismissed", "Dismissed"


class ProjectSpecDocument(TimeStampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="spec_document")
    title = models.CharField(max_length=255, default="Product Spec")
    schema_version = models.PositiveIntegerField(default=1)
    content_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.project.slug}:spec"


class Assumption(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="assumptions")
    title = models.CharField(max_length=255)
    description = models.TextField()
    primary_ref = models.JSONField(default=dict, blank=True)
    impact = models.CharField(max_length=64, default="medium")
    status = models.CharField(max_length=16, choices=AssumptionStatus.choices, default=AssumptionStatus.OPEN)
    source_post = models.ForeignKey(
        "alignment.StreamPost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assumptions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_assumptions",
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_assumptions",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class ProjectRevision(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_revisions",
    )
    source_post = models.ForeignKey(
        "alignment.StreamPost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_revisions",
    )
    source_decision = models.ForeignKey(
        "alignment.Decision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_revisions",
    )
    source_assumption = models.ForeignKey(
        Assumption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_revisions",
    )
    source_agent = models.ForeignKey(
        "agents.AgentSuggestion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_revisions",
    )
    previous_revision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_revisions",
    )

    class Meta:
        ordering = ["number"]
        unique_together = ("project", "number")

    def __str__(self):
        return f"{self.project.slug} r{self.number}"


class SpecDocumentRevision(TimeStampedModel):
    spec_document = models.ForeignKey(ProjectSpecDocument, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_spec_document_revisions",
    )
    project_revision = models.ForeignKey(
        ProjectRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spec_document_revisions",
    )
    previous_revision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_revisions",
    )

    class Meta:
        ordering = ["number"]
        unique_together = ("spec_document", "number")

    def __str__(self):
        return f"{self.spec_document.project.slug} spec r{self.number}"


class ConcernRun(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="concern_runs")
    provider = models.CharField(max_length=64, default="openai")
    model = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=ConcernRunStatus.choices, default=ConcernRunStatus.PENDING)
    concern_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    scopes = models.JSONField(default=list, blank=True)
    trigger = models.CharField(max_length=24, default="manual")
    target_concern_fingerprint = models.CharField(max_length=128, blank=True)
    analyzed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-analyzed_at", "-created_at"]

    def __str__(self):
        return f"{self.project.slug}:{self.provider}:{self.status}"


class ProjectConcern(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="concerns")
    run = models.ForeignKey(
        ConcernRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="concerns",
    )
    source_post = models.ForeignKey(
        "alignment.StreamPost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raised_concerns",
    )
    node_refs = models.JSONField(default=list, blank=True)
    fingerprint = models.CharField(max_length=128)
    concern_type = models.CharField(max_length=32, choices=ConcernType.choices, default=ConcernType.HUMAN_FLAG)
    raised_by_kind = models.CharField(
        max_length=16,
        choices=ConcernRaisedByKind.choices,
        default=ConcernRaisedByKind.SYSTEM,
    )
    title = models.CharField(max_length=255)
    summary = models.TextField()
    severity = models.CharField(max_length=16, choices=ConcernSeverity.choices, default=ConcernSeverity.MEDIUM)
    status = models.CharField(max_length=16, choices=ConcernStatus.choices, default=ConcernStatus.OPEN)
    recommendation = models.TextField(blank=True)
    source_refs = models.JSONField(default=list, blank=True)
    detected_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    reevaluation_requested_at = models.DateTimeField(null=True, blank=True)
    last_reevaluated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_concerns",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_concerns",
    )
    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismissed_concerns",
    )

    class Meta:
        ordering = ["-updated_at", "-detected_at"]
        unique_together = ("project", "fingerprint")

    def __str__(self):
        return self.title


class ConcernProposal(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="concern_proposals")
    concern = models.ForeignKey(ProjectConcern, on_delete=models.CASCADE, related_name="proposals")
    provider = models.CharField(max_length=64, default="openai")
    model = models.CharField(max_length=128, blank=True)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=ConcernProposalStatus.choices, default=ConcernProposalStatus.OPEN)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_concern_proposals",
    )
    created_by_kind = models.CharField(
        max_length=16,
        choices=ConcernRaisedByKind.choices,
        default=ConcernRaisedByKind.AI,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.concern.title} proposal"


class ConcernProposalChange(TimeStampedModel):
    proposal = models.ForeignKey(ConcernProposal, on_delete=models.CASCADE, related_name="changes")
    section_ref = models.JSONField(default=dict, blank=True)
    section_id = models.CharField(max_length=64, blank=True)
    section_title = models.CharField(max_length=255, blank=True)
    original_section_json = models.JSONField(default=dict, blank=True)
    proposed_section_json = models.JSONField(default=dict, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    original_body = models.TextField(blank=True)
    proposed_body = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=ConcernProposalChangeStatus.choices,
        default=ConcernProposalChangeStatus.PENDING,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_concern_proposal_changes",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = ("proposal", "section_id")

    def __str__(self):
        return f"{self.proposal_id}:{self.section_title or self.section_id or 'section-change'}"


class ConsistencyRun(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="consistency_runs")
    provider = models.CharField(max_length=64, default="openai")
    model = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=ConsistencyRunStatus.choices, default=ConsistencyRunStatus.PENDING)
    issue_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    analyzed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-analyzed_at", "-created_at"]

    def __str__(self):
        return f"{self.project.slug}:{self.provider}:{self.status}"


class ConsistencyIssue(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="consistency_issues")
    run = models.ForeignKey(
        ConsistencyRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issues",
    )
    fingerprint = models.CharField(max_length=128)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    severity = models.CharField(
        max_length=16,
        choices=ConsistencyIssueSeverity.choices,
        default=ConsistencyIssueSeverity.MEDIUM,
    )
    status = models.CharField(max_length=16, choices=ConsistencyIssueStatus.choices, default=ConsistencyIssueStatus.OPEN)
    source_refs = models.JSONField(default=list, blank=True)
    recommendation = models.TextField(blank=True)
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-updated_at", "-detected_at"]
        unique_together = ("project", "fingerprint")

    def __str__(self):
        return self.title


class AuditEvent(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    event_type = models.CharField(max_length=40, choices=AuditEventType.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    source_post = models.ForeignKey(
        "alignment.StreamPost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    source_decision = models.ForeignKey(
        "alignment.Decision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    source_assumption = models.ForeignKey(
        Assumption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    source_agent = models.ForeignKey(
        "agents.AgentSuggestion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    project_revision = models.ForeignKey(
        ProjectRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title
