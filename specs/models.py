from django.conf import settings
from django.db import models

from specbridge.model_mixins import TimeStampedModel


class SectionStatus(models.TextChoices):
    ALIGNED = "aligned", "Aligned"
    ITERATING = "iterating", "Iterating"
    BLOCKED = "blocked", "Blocked"


class AssumptionStatus(models.TextChoices):
    OPEN = "open", "Open"
    VALIDATED = "validated", "Validated"
    INVALIDATED = "invalidated", "Invalidated"


class AuditEventType(models.TextChoices):
    VERSION_CREATED = "version_created", "Version Created"
    SECTION_UPDATED = "section_updated", "Section Updated"
    DECISION_APPROVED = "decision_approved", "Decision Approved"
    DECISION_REJECTED = "decision_rejected", "Decision Rejected"
    DECISION_IMPLEMENTED = "decision_implemented", "Decision Implemented"
    ASSUMPTION_VALIDATED = "assumption_validated", "Assumption Validated"
    ASSUMPTION_INVALIDATED = "assumption_invalidated", "Assumption Invalidated"
    AGENT_APPLIED = "agent_applied", "Agent Applied"
    AGENT_DISMISSED = "agent_dismissed", "Agent Dismissed"
    EXPORT_CREATED = "export_created", "Export Created"
    MEMBERSHIP_CHANGED = "membership_changed", "Membership Changed"


class SpecSection(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="sections")
    key = models.SlugField(max_length=64)
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=SectionStatus.choices, default=SectionStatus.ITERATING)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("project", "key")

    def __str__(self):
        return f"{self.project.slug}:{self.title}"


class Assumption(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="assumptions")
    section = models.ForeignKey(
        SpecSection,
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


class SpecVersion(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_spec_versions",
    )
    source_post = models.ForeignKey(
        "alignment.StreamPost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spec_versions",
    )
    source_decision = models.ForeignKey(
        "alignment.Decision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spec_versions",
    )
    source_assumption = models.ForeignKey(
        Assumption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spec_versions",
    )
    source_agent = models.ForeignKey(
        "agents.AgentSuggestion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spec_versions",
    )
    previous_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_versions",
    )

    class Meta:
        ordering = ["number"]
        unique_together = ("project", "number")

    def __str__(self):
        return f"{self.project.slug} v{self.number}"


class AuditEvent(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    event_type = models.CharField(max_length=32, choices=AuditEventType.choices)
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
    spec_version = models.ForeignKey(
        SpecVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title
