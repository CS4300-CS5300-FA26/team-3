"""Issue #22 dashboard warning acceptance steps."""

from datetime import datetime
from decimal import Decimal

from behave import given, then, when


@given("my low-balance threshold is ${amount}")
def set_threshold(context, amount):
    from accounts.models import LowBalanceThreshold

    LowBalanceThreshold.objects.create(owner=context.student, amount=Decimal(amount))


@given("my remaining budget for {month} is ${amount}")
def set_remaining_budget(context, month, amount):
    period = datetime.strptime(month, "%B %Y").date()
    context.month = period.strftime("%Y-%m")
    context.expected_budget = Decimal(amount)
    context.Transaction.objects.create(
        owner=context.student,
        kind=context.Transaction.Kind.INCOME,
        amount=context.expected_budget,
        date=period,
        description="Monthly income",
    )


@when("I view the dashboard")
def view_dashboard(context):
    from django.urls import reverse

    context.response = context.client.get(reverse("dashboard"), {"month": context.month})
    assert context.response.context["remaining_budget"] == context.expected_budget


@then("no low-balance warning is shown")
def no_warning(context):
    assert context.response.status_code == 200
    assert "You are below your" not in context.response.content.decode()
