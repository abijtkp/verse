import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


def validate_full_name(value):
    value = (value or "").strip()

    if not value:
        raise ValidationError(_("Full name is required."))

    if not re.fullmatch(r"^[A-Za-z][A-Za-z0-9 ]*$", value):
        raise ValidationError(
            _("Name must start with a letter and contain only letters, numbers, and spaces.")
        )

    alphabet_count = len(re.findall(r"[A-Za-z]", value))

    if alphabet_count < 4:
        raise ValidationError(
            _("Name must contain at least 4 alphabetic characters.")
        )

class StrongPasswordValidator:
    def validate(self, password, user=None):
        errors = []

        if not re.search(r"[A-Z]", password):
            errors.append(_("Password must contain at least one uppercase letter."))

        if not re.search(r"[a-z]", password):
            errors.append(_("Password must contain at least one lowercase letter."))

        if not re.search(r"\d", password):
            errors.append(_("Password must contain at least one number."))

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append(_("Password must contain at least one special character."))

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Your password must contain uppercase, lowercase, number, and special character."
        )