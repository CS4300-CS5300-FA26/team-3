"""Issue #23 request service; browser behavior remains in the next increment."""
from datetime import datetime, timedelta, timezone
from smtplib import SMTPException
from unittest.mock import patch

from behave import given, then, when
from django.test import override_settings


@given("the reset request service uses local email and a test completion route")
def reset_mail_setup(context):
    settings = override_settings(
        ROOT_URLCONF="tests.reset_urls", SIGNUP_BASE_URL="https://budget-wise.dev",
        MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
    )
    settings.enable()
    context.add_cleanup(settings.disable)
    context.reset_clock = patch("accounts.password_reset_requests.timezone.now")
    context.reset_now = context.reset_clock.start()
    context.add_cleanup(context.reset_clock.stop)
    context.reset_start = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
    context.reset_now.return_value = context.reset_start


@given('a resettable account exists for "{email}"')
def resettable_account(context, email):
    from accounts.identity import create_verified_user

    context.mail_user = create_verified_user(email, "A-tide-of-bright-copper-42!")


@when('the reset request service receives "{email}"')
def request_reset_mail(context, email):
    from accounts.password_reset_requests import request_password_reset

    context.reset_confirmation = request_password_reset(email)


@when('{count:d} reset requests arrive at minute {minute:d}')
def timed_requests(context, count, minute):
    context.reset_now.return_value = context.reset_start + timedelta(minutes=minute)
    for _ in range(count):
        request_reset_mail(context, "student@uccs.edu")


@when("the reset request service receives a request while email is unavailable")
def reset_mail_unavailable(context):
    with patch("accounts.mail.send_mail", side_effect=SMTPException("Unavailable")):
        request_reset_mail(context, "student@uccs.edu")


@when("the reset service is called without the test completion route")
def reset_route_absent(context):
    with override_settings(ROOT_URLCONF="budgetwise.urls"):
        request_reset_mail(context, "student@uccs.edu")


@then('the reset service returns "{message}"')
def reset_confirmation(context, message):
    assert context.reset_confirmation == message


@then('the reset service has sent {count:d} emails')
def reset_email_count(context, count):
    from django.core import mail

    assert len(mail.outbox) == count


@then('the reset email contains a valid thirty-minute token for "{email}"')
def reset_email_credentials(context, email):
    from django.contrib.auth.tokens import default_token_generator
    from django.core import mail
    from django.urls import resolve
    from django.utils.http import urlsafe_base64_decode

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [email]
    link = next(line for line in message.body.splitlines() if line.startswith("https://"))
    match = resolve(link.removeprefix("https://budget-wise.dev"))
    assert int(urlsafe_base64_decode(match.kwargs["uidb64"])) == context.mail_user.pk
    assert default_token_generator.check_token(context.mail_user, match.kwargs["token"])
    assert "30 minutes" in message.body
