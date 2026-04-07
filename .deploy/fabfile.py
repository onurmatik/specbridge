from __future__ import annotations

import base64
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, load_dotenv
from fabric import Connection, task
from invoke import Collection


DEPLOY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DEPLOY_DIR.parent

load_dotenv(DEPLOY_DIR / ".credentials.env")
load_dotenv(DEPLOY_DIR / "deploy.env")


def get_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value is None:
            continue
        value = value.strip()
        if value:
            return value
    return None


def env_value(
    *names: str,
    default: Optional[str] = None,
    required: bool = False,
    hint: Optional[str] = None,
) -> Optional[str]:
    value = get_env(*names)
    if value:
        return value
    if required:
        if hint:
            raise RuntimeError(f"Missing required environment variable: {hint}")
        raise RuntimeError(f"Missing required environment variable: {' or '.join(names)}")
    return default


def require_env(*names: str, hint: Optional[str] = None) -> str:
    value = env_value(*names, required=True, hint=hint)
    assert value is not None
    return value


ENV_GITHUB_APP_REPO = ("GITHUB_APP_REPO",)
ENV_DOMAIN = ("DOMAIN_NAME", "DOMAIN")
ENV_HOST = ("DEPLOY_HOST", "HOST")
ENV_DEPLOY_USER = ("DEPLOY_USER",)
ENV_KEY_FILENAME = ("KEY_FILENAME",)
ENV_PROJECT_NAME = ("PROJECT_NAME",)
ENV_VITE_API_BASE = ("VITE_API_BASE",)
ENV_VITE_SITE_URL = ("VITE_SITE_URL",)
ENV_VITE_OG_IMAGE = ("VITE_OG_IMAGE",)


USER = env_value(*ENV_DEPLOY_USER, default="ubuntu")


PROJECT_NAME = env_value(*ENV_PROJECT_NAME, default=PROJECT_ROOT.name)


def debug(msg: str) -> None:
    print(f"[fab] {msg}")


def get_github_token() -> Optional[str]:
    debug("Refreshing GitHub token via helper script")
    script_path = Path(__file__).resolve().parent / "scripts" / "get_github_app_token.py"
    if not script_path.is_file():
        debug(f"Token helper {script_path} missing")
        return None
    debug(f"Running token helper {script_path}")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        if stderr:
            debug(f"Token helper failed: {stderr}")
        elif stdout:
            debug(f"Token helper failed: {stdout}")
        else:
            debug(f"Token helper failed with exit code {result.returncode}")
        return None
    token = result.stdout.strip()
    if token:
        debug("Fetched GitHub App installation token via helper")
    else:
        debug("Helper returned empty token")
    return token or None


GITHUB_TOKEN = get_github_token()


def get_repo_url() -> str:
    github_repo = require_env(*ENV_GITHUB_APP_REPO)
    return f"https://github.com/{github_repo}.git"


def load_project_env_values() -> dict[str, str]:
    candidates = [
        PROJECT_ROOT / ".env-prod",
        PROJECT_ROOT / ".env",
    ]
    source = next((path for path in candidates if path.is_file()), None)
    if not source:
        return {}

    raw_values = dotenv_values(source)
    values: dict[str, str] = {}
    for key, value in raw_values.items():
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            values[key] = normalized
    debug(f"Loaded project env values from {source}")
    return values


def resolve_frontend_build_env(domain_name: str, project_env: dict[str, str]) -> dict[str, str]:
    def pick(*names: str, default: Optional[str] = None) -> Optional[str]:
        for name in names:
            value = project_env.get(name)
            if value is None:
                value = os.environ.get(name)
            if value is None:
                continue
            normalized = str(value).strip()
            if normalized:
                return normalized
        return default

    api_base = pick("API_BASE_URL", "NEXT_PUBLIC_API_BASE_URL", *ENV_VITE_API_BASE, default=f"https://{domain_name}/api/v1")
    django_base_url = pick("DJANGO_BASE_URL", default=f"https://{domain_name}")
    site_url = pick("NEXT_PUBLIC_SITE_URL", "SITE_URL", *ENV_VITE_SITE_URL, default=f"https://{domain_name}")
    og_image = pick(*ENV_VITE_OG_IMAGE, default=f"{site_url}/og.png")
    turnstile_site_key = pick("NEXT_PUBLIC_TURNSTILE_SITEKEY", "TURNSTILE_SITEKEY")

    build_env = {
        "API_BASE_URL": api_base or "",
        "NEXT_PUBLIC_API_BASE_URL": api_base or "",
        "DJANGO_BASE_URL": django_base_url or "",
        "SITE_URL": site_url or "",
        "NEXT_PUBLIC_SITE_URL": site_url or "",
        "VITE_API_BASE": api_base or "",
        "VITE_SITE_URL": site_url or "",
        "VITE_OG_IMAGE": og_image or "",
    }
    if turnstile_site_key:
        build_env["NEXT_PUBLIC_TURNSTILE_SITEKEY"] = turnstile_site_key
    else:
        debug("WARN: NEXT_PUBLIC_TURNSTILE_SITEKEY is empty; sign-in CAPTCHA may fail in production.")

    return build_env

PROJECT_DIR = f"/srv/apps/{PROJECT_NAME}"
VENV_DIR = f"{PROJECT_DIR}/venv"
PYTHON_BIN = f"{VENV_DIR}/bin/python"
ENV_FILE = f"{PROJECT_DIR}/.env"


def resolve_python_install_command() -> str:
    requirements_file = PROJECT_ROOT / "requirements.txt"
    if requirements_file.is_file():
        return "pip install -r requirements.txt"
    raise RuntimeError("requirements.txt is required for deploy.")


def resolve_frontend_build() -> tuple[Optional[str], Optional[str]]:
    root_package_json = PROJECT_ROOT / "package.json"
    frontend_package_json = PROJECT_ROOT / "frontend" / "package.json"

    if frontend_package_json.is_file():
        return f"{PROJECT_DIR}/frontend", "npm run build"

    if root_package_json.is_file():
        package_text = root_package_json.read_text()
        if '"build:css"' in package_text:
            return PROJECT_DIR, "npm run build:css"
        if '"build"' in package_text:
            return PROJECT_DIR, "npm run build"

    return None, None


def resolve_frontend_install_command(frontend_dir: str) -> str:
    lockfile = frontend_dir.removeprefix(PROJECT_DIR).lstrip("/")
    local_lockfile = PROJECT_ROOT / lockfile / "package-lock.json" if lockfile else PROJECT_ROOT / "package-lock.json"
    if local_lockfile.is_file():
        return "npm ci"
    return "npm install"


def upload_env_file(c) -> None:
    candidates = [
        PROJECT_ROOT / ".env-prod",
        PROJECT_ROOT / ".env",
    ]
    source = next((path for path in candidates if path.is_file()), None)
    if not source:
        debug("No .env file found; skipping environment upload")
        return

    remote_tmp = f"/tmp/{source.name}"
    debug(f"Uploading env file {source} to {ENV_FILE}")
    c.put(str(source), remote_tmp)
    c.sudo(f"mv {remote_tmp} {ENV_FILE}")
    c.sudo(f"chown {USER}:{USER} {ENV_FILE}")
    c.sudo(f"chmod 600 {ENV_FILE}")


def git_with_header(c, git_command: str, token: str, cwd: Optional[str] = None) -> bool:
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    cmd = (
        f'GIT_TERMINAL_PROMPT=0 git -c credential.helper= -c http.extraHeader="Authorization: Basic {auth}" {git_command}'
    )
    location = cwd or "current directory"
    debug(f"Running git command in {location}: git {git_command}")
    if cwd:
        with c.cd(cwd):
            result = c.run(cmd, warn=True)
    else:
        result = c.run(cmd, warn=True)

    if result.failed:
        debug(f"git command failed with exit code {result.return_code}")
        return False
    return True


def run_plain_git(c, git_command: str, cwd: Optional[str] = None) -> None:
    debug(f"Running git command without token: git {git_command}")
    if cwd:
        with c.cd(cwd):
            c.run(f"git {git_command}")
    else:
        c.run(f"git {git_command}")


def run_git_command(c, git_command: str, cwd: Optional[str] = None, use_token: bool = False) -> None:
    global GITHUB_TOKEN
    if use_token and GITHUB_TOKEN:
        debug("Executing git command")
        if git_with_header(c, git_command, GITHUB_TOKEN, cwd=cwd):
            return
        raise RuntimeError("Git command failed")
    else:
        run_plain_git(c, git_command, cwd=cwd)


@task
def deploy(c):
    """Deploy the project to the server."""
    key_filename = require_env(*ENV_KEY_FILENAME)
    host = require_env(*ENV_HOST)
    repo_url = get_repo_url()
    domain_name = require_env(*ENV_DOMAIN)
    project_env_values = load_project_env_values()
    frontend_build_env = resolve_frontend_build_env(domain_name, project_env_values)
    python_install_command = resolve_python_install_command()
    frontend_dir, frontend_build_command = resolve_frontend_build()

    debug(f"Using repo URL: {repo_url}")
    debug(f"Connecting to {USER}@{host} with key {key_filename}")
    c = Connection(
        host=host,
        user=USER,
        connect_kwargs={
            "key_filename": str(Path(f"~/.ssh/{key_filename}").expanduser())
        },
    )

    c.run(f"mkdir -p {PROJECT_DIR}")

    repo_has_git = c.run(f"test -d {PROJECT_DIR}/.git", warn=True).ok
    debug(f"Repo exists on server: {repo_has_git}")

    if not repo_has_git:
        if GITHUB_TOKEN and repo_url.startswith("https://"):
            debug("Cloning repository over HTTPS with token")
            run_git_command(c, f"clone {repo_url} {PROJECT_DIR}", use_token=True)
            c.run(f"git -C {PROJECT_DIR} remote set-url origin {repo_url}")
        else:
            debug(f"Cloning repository using {repo_url}")
            run_git_command(c, f"clone {repo_url} {PROJECT_DIR}")
    else:
        debug("Updating existing repo with hard reset + pull on main")
        use_token = bool(GITHUB_TOKEN and repo_url.startswith("https://"))
        if use_token:
            run_git_command(c, "fetch origin main --prune", cwd=PROJECT_DIR, use_token=True)
        else:
            run_git_command(c, "fetch origin main --prune", cwd=PROJECT_DIR)
        run_git_command(c, "checkout main", cwd=PROJECT_DIR, use_token=False)
        run_git_command(c, "reset --hard origin/main", cwd=PROJECT_DIR, use_token=False)
        if use_token:
            run_git_command(c, "pull --ff-only origin main", cwd=PROJECT_DIR, use_token=True)
        else:
            run_git_command(c, "pull --ff-only origin main", cwd=PROJECT_DIR)

    upload_env_file(c)

    if c.run(f"test -d {VENV_DIR}", warn=True).failed:
        debug("Creating virtualenv")
        c.run(f"python3 -m venv {VENV_DIR}")

    with c.cd(PROJECT_DIR):
        debug(f"Installing Python requirements")
        c.run(f"{VENV_DIR}/bin/pip install --upgrade pip")
        c.run(f"{VENV_DIR}/bin/{python_install_command}")

    if frontend_dir and frontend_build_command:
        frontend_install_command = resolve_frontend_install_command(frontend_dir)
        with c.cd(frontend_dir):
            debug("Installing frontend dependencies")
            c.run(frontend_install_command)
            debug("Building frontend")
            build_env_prefix = " ".join(
                f"{name}={shlex.quote(value)}"
                for name, value in frontend_build_env.items()
                if value
            )
            command = frontend_build_command
            if build_env_prefix:
                command = f"{build_env_prefix} {command}"
            c.run(command)

    with c.cd(PROJECT_DIR):
        debug("Running migrate & collectstatic")
        c.run(f"{PYTHON_BIN} manage.py migrate")
        c.run(f"{PYTHON_BIN} manage.py collectstatic --noinput")

    debug("Restarting services (best effort)")
    c.sudo(
        f"systemctl reset-failed app@{PROJECT_NAME}.service app@{PROJECT_NAME}.socket",
        warn=True,
    )
    c.sudo(f"systemctl restart app@{PROJECT_NAME}.socket", warn=True)
    app_refuse_manual = c.sudo(
        f"systemctl show app@{PROJECT_NAME}.service -p RefuseManualStart --value",
        hide=True,
        warn=True,
    )
    if not app_refuse_manual.failed and app_refuse_manual.stdout.strip().lower() == "yes":
        debug(
            f"Skipping manual restart for app@{PROJECT_NAME}.service "
            "because RefuseManualStart=yes"
        )
    else:
        c.sudo(f"systemctl try-restart app@{PROJECT_NAME}.service", warn=True)
    c.sudo(f"systemctl try-restart node@{PROJECT_NAME}.service", warn=True)
    c.sudo(f"systemctl try-restart celery@{PROJECT_NAME}.service", warn=True)

ns = Collection(deploy)
