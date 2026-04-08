from django.conf import settings
from django.db import models
from django.utils import timezone

from projects.languages import DEFAULT_PROJECT_SPEC_LANGUAGE, PROJECT_SPEC_LANGUAGE_CHOICES
from specbridge.model_mixins import TimeStampedModel


class MembershipRole(models.TextChoices):
    CEO = "ceo", "CEO"
    PRODUCT = "product", "Product"
    ENGINEERING = "engineering", "Engineering"
    DESIGN = "design", "Design"
    VIEWER = "viewer", "Viewer"


class Organization(TimeStampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=255)
    summary = models.TextField()
    status_label = models.CharField(max_length=64, default="Aligning")
    spec_language = models.CharField(
        max_length=16,
        choices=PROJECT_SPEC_LANGUAGE_CHOICES,
        default=DEFAULT_PROJECT_SPEC_LANGUAGE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProjectMembership(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=32, choices=MembershipRole.choices, default=MembershipRole.VIEWER)
    title = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("project", "user")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} @ {self.project}"


class ProjectInvite(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    role = models.CharField(max_length=32, choices=MembershipRole.choices, default=MembershipRole.VIEWER)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_project_invites",
    )
    last_sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def status(self) -> str:
        if self.revoked_at:
            return "revoked"
        if self.accepted_at:
            return "accepted"
        return "pending"

    def __str__(self):
        return f"{self.email} -> {self.project}"

    def mark_sent(self):
        self.last_sent_at = timezone.now()
