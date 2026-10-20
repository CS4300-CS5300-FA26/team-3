"""Issue #18 expense acceptance checks using an isolated Django test database."""

from behave import given, when

from income_steps import signed_in  # reuse the isolated database and login setup


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
