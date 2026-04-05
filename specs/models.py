from django.conf import settings
from django.db import models
from django.utils import timezone

from specbridge.model_mixins import TimeStampedModel


class DocumentStatus(models.TextChoices):
    ALIGNED = "aligned", "Aligned"
    ITERATING = "iterating", "Iterating"
    BLOCKED = "blocked", "Blocked"


class DocumentSourceKind(models.TextChoices):
    PRESET = "preset", "Preset"
    CUSTOM = "custom", "Custom"


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
    CONSISTENCY_RUN_COMPLETED = "consistency_run_completed", "Consistency Run Completed"
    CONSISTENCY_RUN_FAILED = "consistency_run_failed", "Consistency Run Failed"
    CONSISTENCY_ISSUE_RESOLVED = "consistency_issue_resolved", "Consistency Issue Resolved"
    CONSISTENCY_ISSUE_DISMISSED = "consistency_issue_dismissed", "Consistency Issue Dismissed"
    EXPORT_CREATED = "export_created", "Export Created"
    MEMBERSHIP_CHANGED = "membership_changed", "Membership Changed"


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


class ProjectDocument(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="documents")
    slug = models.SlugField(max_length=96)
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=64, choices=DocumentType.choices, default=DocumentType.CUSTOM)
    source_kind = models.CharField(max_length=16, choices=DocumentSourceKind.choices, default=DocumentSourceKind.CUSTOM)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=DocumentStatus.choices, default=DocumentStatus.ITERATING)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("project", "slug")

    def __str__(self):
        return f"{self.project.slug}:{self.title}"


class Assumption(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="assumptions")
    document = models.ForeignKey(
        ProjectDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assumptions",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
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


class DocumentRevision(TimeStampedModel):
    document = models.ForeignKey(ProjectDocument, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_document_revisions",
    )
    project_revision = models.ForeignKey(
        ProjectRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_revisions",
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
        unique_together = ("document", "number")

    def __str__(self):
        return f"{self.document.slug} r{self.number}"


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
