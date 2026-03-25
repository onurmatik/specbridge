from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Q

User = get_user_model()


FIELD_CLASSES = (
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 "
    "placeholder-gray-400 focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
)


class StyledFormMixin:
    def apply_styling(self):
        for field in self.fields.values():
            existing_classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{FIELD_CLASSES} {existing_classes}".strip()


class EmailOrUsernameAuthenticationForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "placeholder": "sarah or sarah@example.com",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )

    error_messages = {
        "invalid_login": "Enter a valid username or email and password.",
        "inactive": "This account is inactive.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styling()

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()
        password = self.cleaned_data.get("password")

        if identifier and password:
            username = (
                User._default_manager.filter(
                    Q(username__iexact=identifier) | Q(email__iexact=identifier)
                )
                .values_list("username", flat=True)
                .first()
                or identifier
            )
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class SignUpForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(
        label="First name",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "given-name",
                "placeholder": "Sarah",
            }
        ),
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "family-name",
                "placeholder": "Stone",
            }
        ),
    )
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "placeholder": "sarah",
            }
        ),
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "you@example.com",
            }
        ),
    )
    organization = forms.CharField(
        label="Organization",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "organization",
                "placeholder": "Acme",
            }
        ),
    )
    title = forms.CharField(
        label="Title",
        max_length=120,
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "organization-title",
                "placeholder": "Product Manager",
            }
        ),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Create a password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Repeat your password",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "organization",
            "title",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styling()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User._default_manager.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.title = self.cleaned_data["title"].strip()
        if commit:
            user.save()
        return user
