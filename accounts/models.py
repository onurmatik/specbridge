from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    title = models.CharField(max_length=120, blank=True)
    avatar_seed = models.CharField(max_length=120, blank=True)

    @property
    def display_name(self) -> str:
        full_name = self.get_full_name().strip()
        return full_name or self.username

    def save(self, *args, **kwargs):
        if not self.avatar_seed:
            self.avatar_seed = self.username or self.email or "specbridge"
        super().save(*args, **kwargs)

    @property
    def avatar_url(self) -> str:
        return (
            "https://api.dicebear.com/7.x/notionists/svg?seed="
            f"{self.avatar_seed}&backgroundColor=transparent"
        )

    def __str__(self):
        return self.display_name
