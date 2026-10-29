"""Issue #23 core scenarios; no email delivery or reset pages yet."""
from datetime import datetime, timedelta
from unittest.mock import patch

from behave import given, then, when


OLD_PASSWORD = "A-tide-of-bright-copper-42!"
NEW_PASSWORD = "Another-wave-of-silver-73!"


@given("a student has a reset token and two signed-in sessions")
def reset_account(context):
    from django.contrib.auth.tokens import default_token_generator
    from django.test import Client
    from accounts.identity import create_verified_user

    context.reset_user = create_verified_user("student@uccs.edu", OLD_PASSWORD)
    context.reset_sessions = [Client(), Client()]
    for client in context.reset_sessions:
        client.force_login(context.reset_user)
    context.reset_user.refresh_from_db()
    context.reset_token = default_token_generator.make_token(context.reset_user)


@given("the student is locked out after five failed sign-ins")
def lock_student(context):
    from django.test import Client
    from django.urls import reverse

    client = Client()
    for _ in range(5):
        client.post(reverse("sign_in"), {"email": context.reset_user.email, "password": "wrong"})
    response = client.post(reverse("sign_in"), {
        "email": context.reset_user.email, "password": OLD_PASSWORD,
    })
    assert "Too many attempts" in response.content.decode()


@when("the password reset core accepts matching new passwords")
def complete_reset(context):
    from accounts.password_reset import complete_password_reset

    complete_password_reset(context.reset_user.pk, context.reset_token, NEW_PASSWORD, NEW_PASSWORD)


@then("the student can sign in only with the new password")
def new_password_works(context):
    from django.test import Client
    from django.urls import reverse

    client = Client()
    response = client.post(reverse("sign_in"), {
        "email": context.reset_user.email, "password": OLD_PASSWORD,
    })
    assert "Email or password is incorrect" in response.content.decode()
    response = client.post(reverse("sign_in"), {
        "email": context.reset_user.email, "password": NEW_PASSWORD,
    })
    assert response.status_code == 302 and response.url == reverse("dashboard")


@then("both previous sessions require sign-in")
def sessions_ended(context):
    from django.urls import reverse

    for client in context.reset_sessions:
        response = client.get(reverse("dashboard"))
        assert response.status_code == 302
        assert response.url == reverse("sign_in") + "?next=/dashboard/"


@when("the password reset core receives a token older than 30 minutes")
def expired_reset(context):
    from django.contrib.auth.tokens import default_token_generator
    from django.core import signing
    from accounts.password_reset import complete_password_reset

    issued_at = datetime(2026, 10, 28, 12)
    with patch.object(default_token_generator, "_now", return_value=issued_at):
        token = default_token_generator.make_token(context.reset_user)
    with patch.object(default_token_generator, "_now", return_value=issued_at + timedelta(seconds=1801)):
        try:
            complete_password_reset(context.reset_user.pk, token, NEW_PASSWORD, NEW_PASSWORD)
        except signing.BadSignature:
            context.reset_rejected = True
        else:
            context.reset_rejected = False


@then("the reset is refused and the old password still works")
def unchanged_password(context):
    assert context.reset_rejected
    context.reset_user.refresh_from_db()
    assert context.reset_user.check_password(OLD_PASSWORD)
