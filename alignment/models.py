import os
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from specbridge.model_mixins import TimeStampedModel


class StreamPostKind(models.TextChoices):
    COMMENT = "comment", "Comment"
    DECISION = "decision", "Decision"
    AGENT = "agent", "Agent"


class StreamAttachmentExtractionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class StreamPostProcessingStatus(models.TextChoices):
    IDLE = "idle", "Idle"
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


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
    processing_status = models.CharField(
        max_length=16,
        choices=StreamPostProcessingStatus.choices,
        default=StreamPostProcessingStatus.IDLE,
    )
    processing_error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.project.slug}: {self.actor_name}"


def stream_attachment_upload_to(instance, filename: str) -> str:
    _, extension = os.path.splitext(filename or "")
    project_slug = slugify(getattr(instance.project, "slug", "")) or "project"
    post_id = getattr(instance.post, "pk", None) or "stream-post"
    return f"stream-attachments/{project_slug}/{post_id}/{uuid.uuid4().hex}{extension.lower()}"


class StreamAttachment(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="stream_attachments")
    post = models.ForeignKey(StreamPost, on_delete=models.CASCADE, related_name="attachments")
    stored_file = models.FileField(upload_to=stream_attachment_upload_to, max_length=500)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    extension = models.CharField(max_length=24, blank=True)
    extracted_text = models.TextField(blank=True)
    extracted_char_count = models.PositiveIntegerField(default=0)
    extraction_status = models.CharField(
        max_length=16,
        choices=StreamAttachmentExtractionStatus.choices,
        default=StreamAttachmentExtractionStatus.PENDING,
    )
    extraction_error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["post", "created_at"]),
        ]

    @property
    def download_url(self) -> str:
        return f"/api/projects/{self.project.slug}/files/{self.id}/download"

    def __str__(self):
        return self.original_name or os.path.basename(self.stored_file.name)


class OpenQuestion(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="questions")
    title = models.CharField(max_length=255)
    details = models.TextField()
    primary_ref = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=16, choices=IssueSeverity.choices, default=IssueSeverity.MEDIUM)
    status = models.CharField(max_length=16, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    source_post = models.ForeignKey(
        StreamPost,
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
    primary_ref = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=16, choices=IssueSeverity.choices, default=IssueSeverity.HIGH)
    status = models.CharField(max_length=16, choices=IssueStatus.choices, default=IssueStatus.OPEN)
    source_post = models.ForeignKey(
        StreamPost,
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
    primary_ref = models.JSONField(default=dict, blank=True)
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
