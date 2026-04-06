from django.conf import settings
from django.db import models

from specbridge.model_mixins import TimeStampedModel


class AgentSuggestionStatus(models.TextChoices):
    OPEN = "open", "Open"
    APPLIED = "applied", "Applied"
    DISMISSED = "dismissed", "Dismissed"


class AgentSuggestion(TimeStampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="agent_suggestions")
    title = models.CharField(max_length=255)
    summary = models.TextField()
    primary_ref = models.JSONField(default=dict, blank=True)
    target_type = models.CharField(max_length=64, default="section")
    target_identifier = models.CharField(max_length=128, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=AgentSuggestionStatus.choices,
        default=AgentSuggestionStatus.OPEN,
    )
    source_post = models.ForeignKey(
        "alignment.StreamPost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_suggestions",
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_agent_suggestions",
    )
    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dismissed_agent_suggestions",
    )
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title
