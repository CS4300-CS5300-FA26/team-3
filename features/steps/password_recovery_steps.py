"""Issue #23's five acceptance scenarios exercise the real public routes."""
from datetime import datetime, timedelta
from unittest.mock import patch

from behave import given, then, when
from django.test import override_settings

from sign_in_lockout_steps import setup_database


OLD_PASSWORD = "A-tide-of-bright-copper-42!"
NEW_PASSWORD = "Another-wave-of-silver-73!"


@given('an account exists for "{email}"')
def recovery_account(context, email):
    from accounts.identity import create_verified_user

    setup_database(context)
    context.recovery_user = create_verified_user(email, OLD_PASSWORD)


@when('I select "Forgot password" and submit "{email}"')
@when('I request another reset for "{email}"')
def public_reset_request(context, email):
    from django.urls import reverse

    request_url = reverse("accounts:forgot_password")
    assert f'href="{request_url}"' in context.client.get(reverse("sign_in")).content.decode()
    assert "Send reset link" in context.client.get(request_url).content.decode()
    with override_settings(SIGNUP_BASE_URL="http://testserver", MAILERS={
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
    }):
        context.response = context.client.post(request_url, {"email": email}, follow=True)


@then("a reset link is sent to that account's email address")
def reset_link_sent(context):
    from django.core import mail
    from django.urls import resolve

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [context.recovery_user.email]
    context.recovery_link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("http://"))
    assert resolve(context.recovery_link.removeprefix("http://testserver")).view_name == "accounts:reset_password"
    assert "New password" in context.client.get(context.recovery_link, follow=True).content.decode()


@then("no reset email is sent")
def no_reset_email(context):
    from django.core import mail

    assert len(mail.outbox) == 0


@given('I hold a valid reset link for "{email}"')
def valid_reset_link(context, email):
    from django.test import Client

    recovery_account(context, email)
    context.old_sessions = [Client(), Client()]
    for client in context.old_sessions:
        client.force_login(context.recovery_user)
    public_reset_request(context, email)
    reset_link_sent(context)


@when("I set a new password of at least 8 characters")
def set_new_password(context):
    response = context.client.get(context.recovery_link, follow=True)
    context.response = context.client.post(response.request["PATH_INFO"], {
        "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD,
    }, follow=True)
    assert "Your password has been reset." in context.response.content.decode()


@then("I can sign in with the new password")
def sign_in_new_password(context):
    from django.test import Client
    from django.urls import reverse

    response = Client().post(reverse("sign_in"), {"email": context.recovery_user.email, "password": NEW_PASSWORD})
    assert response.status_code == 302 and response.url == reverse("dashboard")


@then("the old password is refused")
def refuse_old_password(context):
    from django.test import Client
    from django.urls import reverse

    response = Client().post(reverse("sign_in"), {"email": context.recovery_user.email, "password": OLD_PASSWORD})
    assert "Email or password is incorrect" in response.content.decode()


@then("my other signed-in sessions are signed out")
def invalidate_old_sessions(context):
    from django.urls import reverse

    for client in context.old_sessions:
        response = client.get(reverse("dashboard"))
        assert response.status_code == 302 and response.url.startswith(reverse("sign_in"))


@given('my reset link for "{email}" was sent more than 30 minutes ago')
def expired_link(context, email):
    from django.contrib.auth.tokens import default_token_generator

    recovery_account(context, email)
    with patch.object(default_token_generator, "_now", return_value=datetime.now() - timedelta(seconds=1801)):
        public_reset_request(context, email)
    from django.core import mail

    context.recovery_link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("http://"))


@when("I open the link")
def open_reset_link(context):
    context.response = context.client.get(context.recovery_link, follow=True)


@then("my password is unchanged")
def unchanged_password(context):
    context.recovery_user.refresh_from_db()
    assert context.recovery_user.check_password(OLD_PASSWORD)


@given('5 password resets were requested for "{email}" in the last hour')
def five_requests(context, email):
    from django.core import mail

    recovery_account(context, email)
    for _ in range(5):
        public_reset_request(context, email)
    assert len(mail.outbox) == 5


@then("no new reset email is sent")
def no_extra_email(context):
    from django.core import mail

    assert len(mail.outbox) == 5
