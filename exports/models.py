from django.conf import settings
from django.db import models

from specbridge.model_mixins import TimeStampedModel


class ExportFormat(models.TextChoices):
    PRD = "prd", "Product Requirements"
    TECH_SPEC = "tech_spec", "Technical Spec"
    TASKS = "tasks", "Task Breakdown"
    AGENT = "agent", "Coding Agent Prompt"


class ExportStatus(models.TextChoices):
    READY = "ready", "Ready"
    EXPIRED = "expired", "Expired"
    FAILED = "failed", "Failed"


class ExportArtifact(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="exports")
    format = models.CharField(max_length=24, choices=ExportFormat.choices)
    title = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=ExportStatus.choices, default=ExportStatus.READY)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_exports",
    )
    configuration = models.JSONField(default=dict, blank=True)
    content = models.TextField(blank=True)
    share_enabled = models.BooleanField(default=False)
    share_token = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename
