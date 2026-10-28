"""Registration mail and shared, bounded delivery budgets."""

from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import F, Func, Value
from django.db.models.functions import Lower, Trim
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from accounts.models import SignupRateLimit, UsedVerificationToken
from accounts.verification import VERIFICATION_MAX_AGE, issue_verification_token


EMAIL_LIMIT = 1
EMAIL_WINDOW_SECONDS = 60
IP_LIMIT = 10
IP_WINDOW_SECONDS = 60 * 60


def claim_budget(kind, value, limit, window_seconds, now):
    key = salted_hmac(f"accounts.signup.{kind}", value, algorithm="sha256").hexdigest()
    SignupRateLimit.objects.get_or_create(
        key=key, defaults={"expires_at": now + timedelta(seconds=window_seconds)},
    )
    # Conditional SQL update arbitrates concurrent workers, never process memory.
    return SignupRateLimit.objects.filter(
        key=key, expires_at__gt=now, attempts__lt=limit,
    ).update(attempts=F("attempts") + 1) == 1


def send_signup_email(email, remote_address):
    """Send once within both budgets; throttled submissions succeed silently.

    Transport exceptions propagate to the view's generic retry message. Failed
    deliveries still spend the budget to bound requests against a broken service.
    """
    now = timezone.now()
    SignupRateLimit.objects.filter(expires_at__lte=now).delete()
    # A consumed token is retained through its entire possible validity window.
    UsedVerificationToken.objects.filter(
        consumed_at__lt=now - timedelta(seconds=VERIFICATION_MAX_AGE),
    ).delete()
    if not claim_budget("ip", remote_address, IP_LIMIT, IP_WINDOW_SECONDS, now):
        return
    if not claim_budget("email", email, EMAIL_LIMIT, EMAIL_WINDOW_SECONDS, now):
        return
    # Match the email uniqueness index, including legacy case/space/root-dot forms.
    existing = get_user_model().objects.alias(
        signup_email=Func(Lower(Trim("email")), Value("."), function="RTRIM"),
    ).filter(signup_email=email).exists()
    if existing:
        intro = (
            "We received a request to create a BudgetWise account with this email address. "
            "An account already exists, so there's no need to sign up again."
        )
        path = resolve_url(settings.LOGIN_URL)
        action = "Sign in"
        details = (
            "If you didn't make this request, no action is needed. "
            "Your account and password haven't been changed."
        )
    else:
        token = issue_verification_token(email)
        path = reverse("accounts:verify", args=[token])
        action = "Set your password"
        intro = (
            "Welcome to BudgetWise.\n\n"
            "You're one step away from creating your account. Confirm your email "
            "address and choose a password to get started."
        )
        details = (
            "This link expires in 24 hours and can only be used to create one account.\n\n"
            "If you didn't request a BudgetWise account, you can safely ignore this email. "
            "No account will be created unless you complete this step."
        )
    link = urljoin(settings.SIGNUP_BASE_URL + "/", path)
    body = f"{intro}\n\n{action}:\n{link}\n\n{details}\n\nThe BudgetWise team\n"
    html = render_to_string("accounts/signup_email.html", {
        "intro": intro, "link": link, "action": action, "details": details,
    })
    send_mail("Your BudgetWise signup request", body, settings.DEFAULT_FROM_EMAIL,
              [email], html_message=html)
