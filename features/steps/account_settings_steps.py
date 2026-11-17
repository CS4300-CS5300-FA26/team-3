"""Increment 1 acceptance through Django's local client; no external email."""
from decimal import Decimal
from unittest.mock import patch

from behave import given, then, when


@when("I save an Account safety threshold of ${amount}")
def save_account_threshold(context, amount):
    context.response = context.client.post("/account/", {"amount": amount}, follow=True)


@then("the Account threshold is ${amount}")
def saved_account_threshold(context, amount):
    from accounts.models import LowBalanceThreshold

    assert context.response.status_code == 200
    assert LowBalanceThreshold.objects.get(owner=context.student).amount == Decimal(amount)
    assert "Safety threshold saved." in context.response.content.decode()


@then("the dashboard keeps entry actions without a threshold editor")
def dashboard_entry_actions(context):
    from django.urls import reverse

    response = context.client.get(reverse("dashboard"))
    html = response.content.decode()
    assert 'name="amount"' not in html
    for route in ("record_income", "record_expense"):
        assert html.count(f'href="{reverse(route)}"') == 1


@when("I request a password reset from Account")
def account_recovery(context):
    context.student.email = "student@example.com"
    context.student.set_password("Local-acceptance-password-42!")
    context.student.save(update_fields=["email", "password"])
    context.client.force_login(context.student)
    with patch("accounts.password_reset_requests.send_account_email") as send:
        context.response = context.client.post("/account/", {"action": "reset_password"}, follow=True)
    assert send.call_count == 1
    assert send.call_args.args[0] == context.student.email


@then("Account acknowledges my password reset request")
def neutral_account_recovery(context):
    assert context.response.status_code == 200
    assert "Password reset requested. Check your email for instructions." in context.response.content.decode()


@given("the navigation visitor is {session}")
@given("I am {session} for a missing page")
def missing_page_session(context, session):
    if session == "signed out":
        context.client.logout()


@when("I open a missing application page")
def missing_application_page(context):
    from django.test import override_settings

    with override_settings(DEBUG=False):
        context.response = context.client.get("/missing-budgetwise-page/")


@then("I receive a generic 404 with {destination}")
def generic_missing_page(context, destination):
    assert context.response.status_code == 404
    html = context.response.content.decode()
    assert "Page not found" in html and destination in html
    assert "missing-budgetwise-page" not in html


@then("the Account amount input has no number stepper")
def non_stepping_account_amount(context):
    widget = context.response.context["threshold_form"]["amount"].as_widget()
    assert 'type="text"' in widget
    assert 'inputmode="decimal"' in widget


@when('I visit "{path}" through the shared layout')
def visit_shared_layout(context, path):
    from django.test import override_settings

    with override_settings(DEBUG=False):
        context.response = context.client.get(path)


@then("the header Dashboard link is {visibility}")
def dashboard_link_visibility(context, visibility):
    from django.urls import reverse

    link = f'<a href="{reverse("dashboard")}">Dashboard</a>'
    assert (link in context.response.content.decode()) == (visibility == "visible")
