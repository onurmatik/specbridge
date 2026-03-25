from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, login, logout
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST

from accounts.forms import EmailOrUsernameAuthenticationForm, SignUpForm
from projects.demo import ensure_demo_workspace
from projects.models import Organization
from projects.services import get_primary_project, visible_projects_for_user


def _redirect_target(request: HttpRequest) -> str:
    redirect_to = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME)
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return reverse("project-directory")


def _post_auth_redirect_target(request: HttpRequest, user) -> str:
    redirect_to = _redirect_target(request)
    resolved_path = urlparse(redirect_to).path or redirect_to
    try:
        match = resolve(resolved_path)
    except Resolver404:
        return redirect_to

    slug = match.kwargs.get("slug")
    if slug and not visible_projects_for_user(user).filter(slug=slug).exists():
        primary_project = get_primary_project(user)
        if primary_project is not None:
            return reverse("project-workspace", args=[primary_project.slug])
        return reverse("project-directory")
    return redirect_to


def _create_signup_organization(name: str) -> Organization:
    base_slug = slugify(name) or "organization"
    slug = base_slug
    suffix = 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return Organization.objects.create(name=name, slug=slug)


def _wants_json(request: HttpRequest) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _form_errors(form) -> dict[str, list[str]]:
    return {field: [str(error) for error in errors] for field, errors in form.errors.items()}


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        redirect_to = _redirect_target(request)
        if _wants_json(request):
            return JsonResponse({"ok": True, "redirect_to": redirect_to})
        return redirect(redirect_to)

    ensure_demo_workspace()
    form = EmailOrUsernameAuthenticationForm(request=request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        redirect_to = _post_auth_redirect_target(request, form.get_user())
        if _wants_json(request):
            return JsonResponse({"ok": True, "redirect_to": redirect_to})
        return redirect(redirect_to)

    if request.method == "POST" and _wants_json(request):
        return JsonResponse({"ok": False, "errors": _form_errors(form), "mode": "login"}, status=400)

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "redirect_field_name": REDIRECT_FIELD_NAME,
            "next_url": request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME, ""),
            "logged_out": request.GET.get("logged_out") == "1",
        },
    )


@require_http_methods(["GET", "POST"])
def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        redirect_to = _redirect_target(request)
        if _wants_json(request):
            return JsonResponse({"ok": True, "redirect_to": redirect_to})
        return redirect(redirect_to)

    ensure_demo_workspace()
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            _create_signup_organization(form.cleaned_data["organization"])
        login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
        redirect_to = _post_auth_redirect_target(request, user)
        if _wants_json(request):
            return JsonResponse({"ok": True, "redirect_to": redirect_to})
        return redirect(redirect_to)

    if request.method == "POST" and _wants_json(request):
        return JsonResponse({"ok": False, "errors": _form_errors(form), "mode": "signup"}, status=400)

    return render(
        request,
        "accounts/signup.html",
        {
            "form": form,
            "redirect_field_name": REDIRECT_FIELD_NAME,
            "next_url": request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME, ""),
        },
    )


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    redirect_to = _redirect_target(request)
    if _wants_json(request):
        return JsonResponse({"ok": True, "redirect_to": redirect_to})
    return redirect(redirect_to)
