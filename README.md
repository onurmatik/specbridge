# SpecBridge

SpecBridge is a collaborative, agent-driven product spec system built with Django, Django Ninja, Django templates, and Tailwind CSS.

## Development

```bash
uv sync --python .venv/bin/python
npm install
./.venv/bin/python manage.py migrate
npm run build:css
./.venv/bin/python manage.py runserver
```

## Email Delivery

Local development defaults to Django's `console` email backend, so invitation emails are printed in the terminal that runs `runserver`.

Production defaults to AWS SES over SMTP when `DJANGO_DEBUG=false`. Set these environment variables in production:

```bash
APP_BASE_URL=https://your-domain.example
DEFAULT_FROM_EMAIL="SpecBridge <noreply@your-domain.example>"
INVITATION_FROM_EMAIL="SpecBridge <noreply@your-domain.example>"
AWS_SES_REGION=eu-central-1
AWS_SES_SMTP_USERNAME=your-ses-smtp-username
AWS_SES_SMTP_PASSWORD=your-ses-smtp-password
```

Optional overrides:

```bash
EMAIL_DELIVERY_MODE=ses
AWS_SES_SMTP_HOST=email-smtp.eu-central-1.amazonaws.com
AWS_SES_SMTP_PORT=587
AWS_SES_SMTP_USE_TLS=true
PROJECT_INVITE_MAX_AGE_SECONDS=2592000
```
