from django.core.mail import send_mail
from django.conf import settings
import random, secrets
from datetime import timedelta
from django.utils import timezone
from .models import OTP

def send_otp_email(user, otp_obj, to_email=None):
    subject = "Your OTP Code"
    message = f"Your OTP code is {otp_obj.code}. It will expire in 5 minutes., If you didn't request this, please ignore this email."
    recipient_email = to_email if to_email else user.email 
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient_email],
        fail_silently=False
    )

def generate_otp(user, purpose='signup'):
    code = str(secrets.randbelow(900000) + 100000)
    print(code)

    expiry_time = timezone.now() + timedelta(minutes=5)


    OTP.objects.filter(user=user, purpose=purpose, is_used=False).delete()


    otp_obj = OTP.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expired_at=expiry_time
    )

    return otp_obj