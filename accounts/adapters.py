from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from accounts.models import User


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    
    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        email = user.email

        if not email:
            messages.error(request, "Google login failed.")
            raise ImmediateHttpResponse(redirect('login'))

        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_blocked:
                messages.error(
                    request,
                    "Your account has been blocked.")
                raise ImmediateHttpResponse(redirect('login'))

            sociallogin.connect(request, existing_user)

    def populate_user(self, request, sociallogin, data):

        user = super().populate_user(request, sociallogin, data)

        full_name = data.get("name") or data.get("full_name") or ""
        
        if full_name:
            user.full_name = full_name

        user.is_verified = True
        return user
    

    def save_user(self, request, sociallogin, form=None):
 
        user = super().save_user(request, sociallogin, form)

        if not user.full_name:
            extra_data = sociallogin.account.extra_data
            user.full_name = extra_data.get("name", user.email.split("@")[0])

        user.is_verified = True
        user.save()
        return user