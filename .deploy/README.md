
cd .deploy/
python3 -m pip install -r requirements.txt
fab deploy

# Deploy will upload ../.env-prod (preferred) or ../.env to /srv/apps/{PROJECT_NAME}/.env

# Files
- `.credentials.env`: GitHub App credentials used by `scripts/get_github_app_token.py`
- `deploy.env`: per-project deploy config (PROJECT_NAME, GITHUB_APP_REPO, DEPLOY_HOST, DOMAIN, etc.)
- `requirements.txt`: local deploy tool dependencies for `fab deploy`

# Tip
Copy `.deploy` between projects and only edit `deploy.env` to point at the new repo/host/domain.
