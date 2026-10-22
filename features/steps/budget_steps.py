"""Issue #21 acceptance checks against an isolated demo database."""

from datetime import datetime
from decimal import Decimal
import os
from pathlib import Path
import sys

from behave import given, then, when


@given("an isolated demo dashboard")
def demo_dashboard(context):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
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

    Transaction.objects.all().delete()
    context.client = Client()
    context.client.force_login(get_user_model().objects.create_user(username="budget-student"))
    context.Transaction = Transaction


@given("I have demo income of ${income} and expenses of ${expenses} dated in {month}")
def demo_totals(context, income, expenses, month):
    period = datetime.strptime(month, "%B %Y").date()
    for kind, amount, category in [("income", income, ""), ("expense", expenses, "Food")]:
        context.Transaction.objects.create(
            kind=kind,
            amount=Decimal(amount.replace(",", "")),
            date=period,
            description=f"Demo {kind}",
            category=category,
            is_demo=True,
        )


@given("I have no transactions dated in {month}")
def empty_period(context, month):
    period = datetime.strptime(month, "%B %Y").date()
    assert not context.Transaction.objects.filter(
        date__year=period.year, date__month=period.month
    ).exists()


@when("I view the dashboard with the timeframe set to {month}")
@when("I set the timeframe to {month}")
def select_month(context, month):
    from django.urls import reverse

    period = datetime.strptime(month, "%B %Y").strftime("%Y-%m")
    context.response = context.client.get(reverse("transaction_list"), {"month": period})


@then("I see a remaining budget of ${amount}")
def remaining_budget(context, amount):
    assert context.response.status_code == 200
    assert context.response.context["remaining_budget"] == Decimal(amount)
    assert f"${amount}" in context.response.content.decode()
