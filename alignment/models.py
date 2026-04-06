from django.conf import settings
from django.db import models

from specbridge.model_mixins import TimeStampedModel


class StreamPostKind(models.TextChoices):
    COMMENT = "comment", "Comment"
    DECISION = "decision", "Decision"
    AGENT = "agent", "Agent"


class IssueSeverity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class IssueStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"
    REOPENED = "reopened", "Reopened"


class DecisionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    IMPLEMENTED = "implemented", "Implemented"


class StreamPost(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="stream_posts")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stream_posts",
    )
    actor_name = models.CharField(max_length=120)
    actor_title = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=24, choices=StreamPostKind.choices, default=StreamPostKind.COMMENT)
    concern = models.ForeignKey(
        "specs.ProjectConcern",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.project.slug}: {self.actor_name}"


class OpenQuestion(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="questions")
    title = models.CharField(max_length=255)
    details = models.TextField()
    severity = models.CharField(max_length=16, choices=IssueSeverity.choices, default=IssueSeverity.MEDIUM)
    status = models.CharField(max_length=16, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    source_post = models.ForeignKey(
        StreamPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )
    related_document = models.ForeignKey(
        "specs.ProjectDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raised_questions",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_questions",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_questions",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class Blocker(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="blockers")
    title = models.CharField(max_length=255)
    details = models.TextField()
    severity = models.CharField(max_length=16, choices=IssueSeverity.choices, default=IssueSeverity.HIGH)
    status = models.CharField(max_length=16, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    source_post = models.ForeignKey(
        StreamPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blockers",
    )
    related_document = models.ForeignKey(
        "specs.ProjectDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blockers",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_blockers",
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raised_blockers",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_blockers",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class Decision(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="decisions")
    code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    status = models.CharField(max_length=16, choices=DecisionStatus.choices, default=DecisionStatus.PENDING)
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposed_decisions",
    )
    source_post = models.ForeignKey(
        StreamPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
    )
    related_document = models.ForeignKey(
        "specs.ProjectDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
    )
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overridden_by",
    )
    implementation_progress = models.PositiveSmallIntegerField(default=0)
    approved_at = models.DateTimeField(null=True, blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            project_code = self.project.slug.replace("-", "").upper()[:4] or "PRJ"
            sequence = Decision.objects.filter(project=self.project).exclude(pk=self.pk).count() + 1
            self.code = f"{project_code}-{sequence:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class DecisionApproval(TimeStampedModel):
    decision = models.ForeignKey(Decision, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="decision_approvals",
    )
    approved = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("decision", "approver")

    def __str__(self):
        return f"{self.approver} -> {self.decision}"
