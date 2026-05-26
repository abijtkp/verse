import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTP


logger = logging.getLogger(__name__)


def send_otp_email(user, otp_obj, to_email=None):
    recipient_email = to_email if to_email else user.email
    user_name = user.full_name or "VERSE Customer"

    purpose_text = {
        "signup": "complete your VERSE account verification",
        "reset_password": "reset your VERSE account password",
        "email_change": "confirm your new email address",
    }.get(otp_obj.purpose, "verify your VERSE account")

    subject = "VERSE Verification Code"

    message = f"""
Hi {user_name},

Your VERSE verification code is:

{otp_obj.code}

Use this code to {purpose_text}.

This code will expire in 5 minutes.

If you did not request this code, you can safely ignore this email.

VERSE Security Team
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
        )

        logger.info(
            "OTP email sent successfully | user_id=%s | email=%s | purpose=%s",
            user.id,
            recipient_email,
            otp_obj.purpose,
        )

    except Exception:
        logger.exception(
            "Failed to send OTP email | user_id=%s | email=%s | purpose=%s",
            user.id,
            recipient_email,
            otp_obj.purpose,
        )
        raise


def generate_otp(user, purpose="signup"):
    code = str(secrets.randbelow(900000) + 100000)
    expiry_time = timezone.now() + timedelta(minutes=5)

    deleted_count, _ = OTP.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
    ).delete()

    otp_obj = OTP.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expired_at=expiry_time,
    )

    logger.info(
        "OTP generated | user_id=%s | purpose=%s | expires_at=%s | old_unused_otps_deleted=%s",
        user.id,
        purpose,
        expiry_time,
        deleted_count,
    )

    return otp_obj