"""Issue #12 income acceptance checks. Shared steps are in common_steps.py."""

from behave import when

from common_steps import money, remember_budget_before


@when('I add income of ${amount} dated {date} with source "{source}"')
def add_income(context, amount, date, source):
    from django.urls import reverse

    remember_budget_before(context, source, date)
    context.response = context.client.post(
        reverse("record_income"),
        {"amount": money(amount), "date": date, "description": source},
    )
