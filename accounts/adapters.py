from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from accounts.models import User


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Runs before social login is processed.
        If a local user with the same email already exists, connect to that user.
        Also block users marked as blocked.
        """
        user = sociallogin.user
        email = user.email

        if not email:
            return

        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_blocked:
                raise PermissionDenied("This account is blocked.")

            # Connect Google login to existing local user
            sociallogin.connect(request, existing_user)

    def populate_user(self, request, sociallogin, data):
        """
        Fill custom user fields from Google data before saving.
        """
        user = super().populate_user(request, sociallogin, data)

        full_name = data.get("name") or data.get("full_name") or ""
        if full_name:
            user.full_name = full_name

        user.is_verified = True
        return user

    def save_user(self, request, sociallogin, form=None):
        """
        Save user with custom project rules.
        """
        user = super().save_user(request, sociallogin, form)

        if not user.full_name:
            extra_data = sociallogin.account.extra_data
            user.full_name = extra_data.get("name", user.email.split("@")[0])

        user.is_verified = True
        user.save()
        return user