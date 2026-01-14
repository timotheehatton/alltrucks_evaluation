from django.contrib.auth.backends import ModelBackend
from .models import User


class CaseInsensitiveEmailBackend(ModelBackend):
    """
    Custom authentication backend that allows case-insensitive email login.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None

        # Normalize email to lowercase
        email = username.lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None