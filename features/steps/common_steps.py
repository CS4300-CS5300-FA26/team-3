"""Steps and helpers shared by the income and expense features: an isolated
test database with a signed-in student, response and saved-row checks, and the
dashboard checks used by the success scenarios."""

from decimal import Decimal
import os
from pathlib import Path
import sys

from behave import given, then


@given("I am signed in")
def signed_in(context):
    src = Path(__file__).resolve().parents[2] / "src"
    sys.path.insert(0, str(src))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgetwise.settings")

    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.test.runner import DiscoverRunner
    from transactions.models import Transaction

    runner = DiscoverRunner(verbosity=0, interactive=False)
    runner.setup_test_environment()
    context.add_cleanup(runner.teardown_test_environment)
    databases = runner.setup_databases()
    context.add_cleanup(runner.teardown_databases, databases)

    student = get_user_model().objects.create_user(username="student")
    context.client = Client()
    context.client.force_login(student)
    context.transaction_count = Transaction.objects.count()
    context.Transaction = Transaction


def money(amount):
    """Turn "1,200.00" from a scenario into "1200.00" for a form."""
    return amount.replace(",", "")


def remaining_budget(context, month):
    from django.urls import reverse

    response = context.client.get(reverse("transaction_list"), {"month": month})
    return response.context["remaining_budget"]


def remember_budget_before(context, description, date):
    """Record the entry and its month's budget before a When step posts it."""
    context.entry = description
    context.month = date[:7]
    context.budget_before = remaining_budget(context, context.month)


@then('I see "{message}"')
def see_message(context, message):
    assert context.response.status_code == 200
    assert message in context.response.content.decode(), f"Expected {message!r} in the response"


@then("no entry is created")
def no_entry(context):
    assert context.Transaction.objects.count() == context.transaction_count


@then("the entry appears in my transaction list")
def entry_listed(context):
    from django.urls import reverse

    # Look for the saved row itself: the demo data already has a "Part-time job".
    saved = context.Transaction.objects.get(is_demo=False, description=context.entry)
    response = context.client.get(reverse("transaction_list"), {"month": context.month})
    assert saved in response.context["transactions"], f"{context.entry!r} is not listed"


@then("my remaining budget increases by ${amount}")
def budget_increases(context, amount):
    change = remaining_budget(context, context.month) - context.budget_before
    assert change == Decimal(money(amount)), f"Budget changed by {change}"


@then("my remaining budget decreases by ${amount}")
def budget_decreases(context, amount):
    change = context.budget_before - remaining_budget(context, context.month)
    assert change == Decimal(money(amount)), f"Budget changed by {change}"
