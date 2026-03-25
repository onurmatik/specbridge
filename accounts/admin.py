from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SpecBridgeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("SpecBridge", {"fields": ("title", "avatar_seed")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "title", "is_staff")
