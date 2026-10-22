from behave import given, then, when
from django.test import override_settings

from verification_steps import PASSWORD


@when("the student requests signup while the email service is unavailable")
def unavailable_email(context):
    from smtplib import SMTPException
    from unittest.mock import patch

    with patch("accounts.signup.send_mail", side_effect=SMTPException("Unavailable")):
        request_signup(context, "student@example.org")


@then("signup shows the email error and an enabled Continue button")
def signup_retry(context):
    from django.test import SimpleTestCase

    check = SimpleTestCase()
    check.assertContains(context.signup_response, "Unable to send email right now.")
    check.assertContains(context.signup_response,
        '<button type="submit" data-pending-label="Sending email…">Continue</button>', html=True)


@given('signup already has an account for "{email}"')
def existing_account(context, email):
    from accounts.identity import create_verified_user

    create_verified_user(email, PASSWORD)


@when('the student requests signup for "{email}"')
def request_signup(context, email):
    from django.test import Client
    from django.urls import reverse

    with override_settings(
        MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
        SIGNUP_BASE_URL="https://budget-wise.dev",
    ):
        context.signup_client = Client()
        context.signup_response = context.signup_client.post(reverse("accounts:signup"), {"email": email})


@then("signup displays the generic Check your email page")
def confirmation(context):
    from django.urls import reverse

    assert context.signup_response.status_code == 302
    assert context.signup_response.url == reverse("accounts:check_email")
    assert "Check your email" in context.signup_client.get(context.signup_response.url).content.decode()


@then("signup emails a verification link without creating an account")
def emailed_link(context):
    from django.contrib.auth import get_user_model
    from django.core import mail

    assert get_user_model().objects.count() == 0
    assert len(mail.outbox) == 1
    link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("https://"))
    assert link.startswith("https://budget-wise.dev/accounts/verify/")
    context.verification_token = link.split("/verify/")[1].rstrip("/")


@then("signup emails the existing owner a notice without a verification link")
def emailed_notice(context):
    from django.contrib.auth import get_user_model
    from django.core import mail

    assert len(mail.outbox) == 1
    assert "already exists" in mail.outbox[0].body
    assert "/verify/" not in mail.outbox[0].body
    assert get_user_model().objects.count() == 1


@when("the new student signs in and records income and an expense")
def sign_in_and_record(context):
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    context.site_client = context.registration_client
    response = context.site_client.post(reverse("sign_in"), {
        "email": get_user_model().objects.get().email, "password": PASSWORD,
    })
    assert response.status_code == 302 and response.url == reverse("dashboard")
    for route, data in [
        ("record_income", {"amount": "1200", "date": "2026-10-22", "description": "My pay"}),
        ("record_expense", {"amount": "12", "date": "2026-10-22", "description": "My lunch", "category": "Food", "is_fixed": "variable"}),
    ]:
        response = context.site_client.post(reverse(route), data)
        assert response.status_code == 302 and response.url == reverse(route)


@then("the dashboard shows only the student's saved entries")
def own_dashboard(context):
    from django.urls import reverse
    from transactions.models import Transaction

    response = context.site_client.get(reverse("dashboard"), {"month": "2026-10"})
    saved = list(response.context["transactions"])
    assert {entry.description for entry in saved} == {"My pay", "My lunch"}
    assert all(entry.owner_id == int(context.site_client.session["_auth_user_id"]) for entry in saved)
    assert Transaction.objects.filter(is_demo=True).exists()


@when("the student signs out of BudgetWise")
def sign_out(context):
    from django.urls import reverse

    response = context.site_client.post(reverse("sign_out"))
    assert response.status_code == 302 and response.url == reverse("sign_in")
    assert "_auth_user_id" not in context.site_client.session


@then("protected pages lead to the sign-in screen")
def protected_after_signout(context):
    from django.urls import reverse

    for route in ["dashboard", "record_income", "record_expense"]:
        response = context.site_client.get(reverse(route), follow=True)
        assert response.status_code == 200
        assert response.request["PATH_INFO"] == reverse("sign_in")
