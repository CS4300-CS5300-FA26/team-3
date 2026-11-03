"""D12 reset requests and rolling-hour delivery admissions, without public views.

PR 3 must supply accounts:reset_password with uidb64/token keyword arguments.
Until that route exists this service sends no mail. Its view must display the
same confirmation for every outcome; synchronous delivery still differs in timing.
"""
from datetime import timedelta
from smtplib import SMTPException

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Func, Value
from django.db.models.functions import Lower, Trim
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.debug import sensitive_variables

from accounts.identity import normalize_email
from accounts.mail import send_account_email
from accounts.models import PasswordResetRateLimit


RESET_CONFIRMATION = "If an account matches, password reset instructions will be sent"


def _claim_reset_request(email):
    # Cleanup outside the per-key transaction avoids locking other keys while
    # holding this one. Expiry is the most recent admission plus one hour.
    PasswordResetRateLimit.objects.filter(expires_at__lte=timezone.now()).delete()
    key = salted_hmac("accounts.password_reset", email, algorithm="sha256").hexdigest()
    with transaction.atomic():
        # A write before any read also serializes file-backed SQLite, which has
        # no SELECT FOR UPDATE. PostgreSQL locks the row instead of the database.
        PasswordResetRateLimit.objects.filter(pk=key).update(key=F("key"))
        PasswordResetRateLimit.objects.get_or_create(
            key=key, defaults={"expires_at": timezone.now() + timedelta(hours=1)},
        )
        budget = PasswordResetRateLimit.objects.select_for_update().get(pk=key)
        now = timezone.now()  # Sample after waiting for the lock.
        cutoff = (now - timedelta(hours=1)).timestamp()
        recent = [timestamp for timestamp in budget.admitted_at if timestamp > cutoff]
        if len(recent) >= 5:
            return False
        budget.admitted_at = [*recent, now.timestamp()]
        budget.expires_at = now + timedelta(hours=1)
        budget.save(update_fields=["admitted_at", "expires_at"])
    return True


@sensitive_variables()
def request_password_reset(email):
    """Admit before lookup; failed delivery also spends the email's budget.

    Known, unknown, ineligible, throttled and transport-failed requests return
    the same text. Unexpected code/database errors propagate for diagnosis.
    No password, session or lockout state changes until reset completion.
    """
    try:
        email = normalize_email(email)
    except ValidationError:
        return RESET_CONFIRMATION
    if not _claim_reset_request(email):
        return RESET_CONFIRMATION
    # Match the existing account email uniqueness index, including legacy forms.
    user = get_user_model().objects.alias(
        reset_email=Func(Lower(Trim("email")), Value("."), function="RTRIM"),
    ).filter(reset_email=email, is_active=True).first()
    if user is None or not user.has_usable_password():
        return RESET_CONFIRMATION
    token = default_token_generator.make_token(user)
    try:
        path = reverse("accounts:reset_password", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": token,
        })
    except NoReverseMatch:
        return RESET_CONFIRMATION
    try:
        send_account_email(
            email, "Reset your BudgetWise password", path,
            "We received a request to reset your BudgetWise password.",
            "Reset your password",
            "This link expires in 30 minutes.\n\n"
            "If you didn't request a password reset, you can safely ignore this email. "
            "Your password will stay the same unless you complete the reset.",
        )
    except (SMTPException, OSError):
        # Never expose transport errors or log their potentially secret payloads.
        pass
    return RESET_CONFIRMATION
