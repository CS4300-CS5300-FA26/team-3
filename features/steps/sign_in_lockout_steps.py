
"""Behave steps for issue #11: sign in, sign out, and lockout."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from behave import given, when, then


EMAIL = "student@uccs.edu"
PASSWORD = "A-tide-of-bright-copper-42!"


def setup_database(context):
    """Create an isolated Django test database for the scenario."""
    import os
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    sys.path.insert(0, str(src))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgetwise.settings")

    import django
    django.setup()

    from django.test import Client
    from django.test.runner import DiscoverRunner

    runner = DiscoverRunner(verbosity=0, interactive=False)
    runner.setup_test_environment()
    context.add_cleanup(runner.teardown_test_environment)

    databases = runner.setup_databases()
    context.add_cleanup(runner.teardown_databases, databases)

    context.client = Client()


def create_student(context, email=EMAIL):
    from django.contrib.auth import get_user_model

    context.student = get_user_model().objects.create_user(
        username=email,
        email=email,
        password=PASSWORD,
    )


def submit_sign_in(context, email, password):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("sign_in"),
        {"email": email, "password": password},
    )


@given("I have an account with 3 saved transactions")
def three_saved_transactions(context):
    # Set up the test database and create the student
    setup_database(context)
    create_student(context)

    from django.utils import timezone
    from transactions.models import Transaction

    # Create three transactions for the student
    context.descriptions = [
        "My Grocery Purchase",
        "My Part-time Paycheck",
        "My Bus Fare",
    ]

    for description in context.descriptions:
        Transaction.objects.create(
            owner=context.student,
            kind=Transaction.Kind.INCOME,
            amount=Decimal("20.00"),
            date=timezone.localdate(),
            description=description,
            category="Other",
            is_demo=False,
        )

@when("I sign in with the correct email and password")
def correct_sign_in(context):
    submit_sign_in(context, EMAIL, PASSWORD)


@then("I see my dashboard")
def see_dashboard(context):
    from django.urls import reverse

    assert context.response.status_code == 302
    assert context.response.url == reverse("dashboard")

    context.dashboard_response = context.client.get(
        reverse("dashboard")
    )
    assert context.dashboard_response.status_code == 200


@then("my 3 transactions are listed")
def three_transactions_listed(context):
    transactions = list(
        context.dashboard_response.context["transactions"]
    )

    assert len(transactions) == 3
    assert {
        transaction.description for transaction in transactions
    } == set(context.descriptions)


@given('I have an account with email "{email}"')
def existing_account(context, email):
    setup_database(context)
    create_student(context, email)


@when('I sign in with "{email}" and an incorrect password')
def wrong_password(context, email):
    submit_sign_in(context, email, "WrongPassword123!")


@then("I remain on the sign-in screen")
def remain_on_sign_in(context):
    from django.urls import reverse

    assert context.response.status_code == 200
    assert "_auth_user_id" not in context.client.session
    assert context.response.request["PATH_INFO"] == reverse("sign_in")


@given('no account exists for "{email}"')
def unknown_account(context, email):
    from django.contrib.auth import get_user_model

    setup_database(context)
    assert not get_user_model().objects.filter(email=email).exists()


@when('I sign in with "{email}" and any password')
def unknown_email_sign_in(context, email):
    submit_sign_in(context, email, "AnyPassword123!")


@then('I see a "Create account" link')
def create_account_link(context):
    assert context.response.status_code == 200
    assert "Create account" in context.response.content.decode()


@when("I select Sign out")
def select_sign_out(context):
    from django.urls import reverse

    context.response = context.client.post(reverse("sign_out"))


@then("I am returned to the sign-in screen")
def returned_to_sign_in(context):
    from django.urls import reverse

    assert context.response.status_code == 302
    assert context.response.url == reverse("sign_in")
    assert "_auth_user_id" not in context.client.session


@then("my dashboard is not reachable without signing in again")
def dashboard_requires_login(context):
    from django.urls import reverse

    response = context.client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("sign_in"))


@given('5 failed sign-ins for "{email}" in the last 15 minutes')
def five_recent_failures(context, email):
    from accounts.models import LoginAttempt, FailedSignIn
    from django.utils import timezone

    setup_database(context)
    create_student(context, email)

    now = timezone.now()

    for _ in range(5):
        FailedSignIn.objects.create(
            email=email,
            created_at=now - timedelta(minutes=1),
        )

    LoginAttempt.objects.create(
        email=email,
        failed_count=5,
        first_failed_at=now - timedelta(minutes=1),
        blocked_until=now + timedelta(minutes=15),
    )


@when("I sign in again with any password")
def retry_during_lockout(context):
    with patch("accounts.lockout.authenticate") as mock_authenticate:
        submit_sign_in(context, EMAIL, PASSWORD)
        context.password_was_checked = mock_authenticate.called


@then("the password is not checked")
def password_not_checked(context):
    assert not context.password_was_checked
