"""Issue #28 acceptance steps for a student's custom notice window."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from behave import given, then, when


@given("I have a monthly Rent schedule due on {due} for notice settings")
def rent_schedule(context, due):
    context.schedule = context.Transaction.objects.create(
        owner=context.student,
        kind=context.Transaction.Kind.EXPENSE,
        amount=Decimal("650.00"),
        date=date(2026, 10, 1),
        description="Rent",
        category="Housing",
        is_fixed=True,
        recurrence=context.Transaction.Recurrence.MONTHLY,
        next_due_date=date.fromisoformat(due),
    )


def submit_notice(context, days):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("edit_transaction", args=[context.schedule.pk]),
        {
            "amount": "650.00",
            "date": "2026-10-01",
            "description": "Rent",
            "category": "Housing",
            "is_fixed": "fixed",
            "recurrence": "monthly",
            "next_due_date": "2026-11-01",
            "reminder_days": days,
        },
    )


@when("I save a {days}-day notice for Rent")
def save_notice(context, days):
    submit_notice(context, days)
    assert context.response.status_code == 302, "The notice was not saved"


@when("I submit a {days}-day notice for Rent")
def invalid_notice(context, days):
    submit_notice(context, days)


@when("I view the Rent reminder on {today}")
def view_notice(context, today):
    from django.urls import reverse

    with patch("accounts.views.timezone.localdate", return_value=date.fromisoformat(today)):
        context.response = context.client.get(reverse("dashboard"))


@when("I record the matching Rent payment on {paid_on}")
def record_matching_payment(context, paid_on):
    from django.urls import reverse

    response = context.client.post(
        reverse("record_expense"),
        {
            "amount": "650.00",
            "date": paid_on,
            "description": "Rent",
            "category": "Housing",
            "is_fixed": "fixed",
            "recurrence": "",
            "next_due_date": "",
        },
    )
    assert response.status_code == 302, "The payment was not saved"


@then("no Rent reminder appears for the selected notice")
def no_notice(context):
    assert context.response.status_code == 200
    assert "Rent of $650.00 is due" not in context.response.content.decode()


@then("the reminder notice field shows a validation error")
def notice_validation_error(context):
    assert context.response.status_code == 200
    assert "reminder_days" in context.response.context["form"].errors
