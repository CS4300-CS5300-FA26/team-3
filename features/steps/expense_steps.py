"""Issue #18 expense acceptance checks using an isolated Django test database."""

from behave import given, when

# Reuse the isolated database, login setup, and success-scenario helpers.
from income_steps import money, remember_budget_before, signed_in


@given("I am signed in to record expenses")
def signed_in_for_expenses(context):
    signed_in(context)


@when("I add an expense of ${amount} with no category selected")
def add_expense_without_category(context, amount):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("record_expense"),
        {"amount": amount, "date": "2026-10-01", "description": "Snack", "category": "", "is_fixed": "variable"},
    )


@when('I add an expense of ${amount} for "{description}" in category {category} marked {kind}')
def add_expense(context, amount, description, category, kind):
    from django.urls import reverse

    remember_budget_before(context, description, "2026-10-01")
    context.response = context.client.post(
        reverse("record_expense"),
        {
            "amount": money(amount),
            "date": "2026-10-01",
            "description": description,
            "category": category,
            "is_fixed": kind.lower(),
        },
    )
