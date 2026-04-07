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

Production defaults to `django-ses` when `DJANGO_DEBUG=false`. Set these environment variables in production:

```bash
APP_BASE_URL=https://your-domain.example
DEFAULT_FROM_EMAIL="SpecBridge <hello@specbridge.io>"
INVITATION_FROM_EMAIL="SpecBridge <invite@specbridge.io>"
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

If the app runs on EC2, ECS, or another AWS environment with an IAM role, the access key variables are optional as long as boto3 can resolve credentials from the default AWS credential chain.

Optional overrides:

```bash
EMAIL_DELIVERY_MODE=ses
AWS_SES_REGION_NAME=us-east-1
AWS_SES_REGION_ENDPOINT=email.us-east-1.amazonaws.com
USE_SES_V2=false
PROJECT_INVITE_MAX_AGE_SECONDS=2592000
```
