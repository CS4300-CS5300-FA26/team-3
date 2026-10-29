"""D12 password reset completion; email delivery and public views are separate.

Call with a decoded user ID and a Django default_token_generator token.
BadSignature covers invalid, expired, used and ineligible-account links;
ValidationError contains Django's password form errors. Database failures propagate.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.views.decorators.debug import sensitive_variables

from accounts.identity import normalize_email
from accounts.models import FailedSignIn, LoginAttempt


@sensitive_variables()
@transaction.atomic
def complete_password_reset(user_id, token, password, password_confirmation):
    """Change only the password and clear sign-in failures in one transaction.

    Re-read and validate under the user lock so concurrent reset submissions
    cannot both succeed. Sessions invalidate through Django's auth hash check.
    """
    users = get_user_model().objects
    if connection.vendor == "sqlite":
        # SQLite lacks row locks: acquire its write lock before reading state.
        users.filter(pk=user_id).update(password=F("password"))
    try:
        user = users.get(pk=user_id)
        # Match sign-in/cleanup lock order: LoginAttempt before the user or failures.
        email = normalize_email(user.email)
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(email=email)
        user = users.select_for_update().get(pk=user_id)
    except (get_user_model().DoesNotExist, ValidationError):
        raise signing.BadSignature("Invalid password reset link.") from None
    if (not user.is_active or not user.has_usable_password()
            or not default_token_generator.check_token(user, token)):
        raise signing.BadSignature("Invalid password reset link.")

    form = SetPasswordForm(user, {
        "new_password1": password, "new_password2": password_confirmation,
    })
    if not form.is_valid():
        raise ValidationError(form.errors.as_data())
    form.save(commit=False)
    user.save(update_fields=["password"])
    attempt.failed_count = 0
    attempt.first_failed_at = None
    attempt.blocked_until = None
    attempt.save(update_fields=["failed_count", "first_failed_at", "blocked_until"])
    FailedSignIn.objects.filter(email=email).delete()
    return user
