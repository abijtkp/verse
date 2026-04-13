from django.core.mail import send_mail
from django.conf import settings
import random
from datetime import timedelta
from django.utils import timezone
from .models import OTP

def send_otp_email(user, otp_obj):
    subject = "Your OTP Code"
    message = f"Your OTP code is {otp_obj.code}. It will expire in 5 minutes."

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False
    )


def generate_otp(user):
    # 1. Generate 6-digit OTP
    code = str(random.randint(100000, 999999))

    # 2. Expiry time (5 minutes)
    expiry_time = timezone.now() + timedelta(minutes=5)

    # 3. Delete old OTPs for same email (important)
    OTP.objects.filter(user=user, is_used=False).delete()

    # 4. Create new OTP record
    otp_obj = OTP.objects.create(
        user=user,
        code=code,
        expired_at=expiry_time
    )

    return otp_obj