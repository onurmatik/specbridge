from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from projects.models import ProjectInvite

logger = logging.getLogger(__name__)

INVITE_SIGNING_SALT = "projects.invite"


class InviteTokenError(Exception):
    pass


class InviteTokenExpired(InviteTokenError):
    pass


@dataclass
class InviteEmailContext:
    invite: ProjectInvite
    accept_url: str
    invited_by_name: str
    project_name: str
    project_tagline: str
    role_label: str
    is_resend: bool


def invitation_token(invite: ProjectInvite) -> str:
    return signing.dumps({"invite_id": invite.id}, salt=INVITE_SIGNING_SALT)


def get_invite_for_token(token: str) -> ProjectInvite:
    try:
        payload = signing.loads(
            token,
            salt=INVITE_SIGNING_SALT,
            max_age=settings.PROJECT_INVITE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise InviteTokenExpired("Invitation link has expired.") from exc
    except signing.BadSignature as exc:
        raise InviteTokenError("Invitation link is invalid.") from exc

    try:
        return ProjectInvite.objects.select_related("project", "invited_by").get(pk=payload["invite_id"])
    except ProjectInvite.DoesNotExist as exc:
        raise InviteTokenError("Invitation no longer exists.") from exc


def build_invite_accept_url(invite: ProjectInvite, request=None) -> str:
    path = reverse("project-invite-accept", args=[invitation_token(invite)])
    if request is not None:
        return request.build_absolute_uri(path)
    if settings.APP_BASE_URL:
        return f"{settings.APP_BASE_URL.rstrip('/')}{path}"
    return path


def send_project_invitation_email(invite: ProjectInvite, request=None, *, is_resend: bool = False) -> None:
    accept_url = build_invite_accept_url(invite, request=request)
    context = InviteEmailContext(
        invite=invite,
        accept_url=accept_url,
        invited_by_name=invite.invited_by.display_name if invite.invited_by else "A teammate",
        project_name=invite.project.name,
        project_tagline=(invite.project.tagline or "").strip(),
        role_label=invite.get_role_display(),
        is_resend=is_resend,
    )
    subject_prefix = "Reminder: " if is_resend else ""
    subject = f"{settings.EMAIL_SUBJECT_PREFIX}{subject_prefix}{context.invited_by_name} invited you to {context.project_name}"
    text_body = render_to_string("emails/project_invite.txt", {"email": context})
    html_body = render_to_string("emails/project_invite.html", {"email": context})
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.INVITATION_FROM_EMAIL,
        to=[invite.email],
        reply_to=[invite.invited_by.email] if invite.invited_by and invite.invited_by.email else None,
    )
    message.attach_alternative(html_body, "text/html")
    logger.info("Sending project invitation email", extra={"invite_id": invite.id, "email": invite.email})
    message.send(fail_silently=False)
