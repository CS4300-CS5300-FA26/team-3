"""D14 acceptance steps for daily and weekly fixed expense reminders."""

from datetime import date
from unittest.mock import patch

from behave import then, when
from django.urls import reverse


@when("I save a fixed expense with a {frequency} schedule due on {due}")
def save_frequency(context, frequency, due):
    context.frequency = frequency
    context.description = f"{frequency.title()} pass"
    context.response = context.client.post(
        reverse("record_expense"),
        {
            "amount": "25.00",
            "date": "2026-10-01",
            "description": context.description,
            "category": "Transportation",
            "is_fixed": "fixed",
            "recurrence": frequency,
            "next_due_date": due,
        },
    )
    assert context.response.status_code == 302, "The schedule was not saved"
    context.schedule = context.Transaction.objects.get(
        owner=context.student, description=context.description
    )


@then("the {frequency} expense is due in 2 days on the dashboard")
def reminder_appears(context, frequency):
    with patch("accounts.views.timezone.localdate", return_value=date(2026, 10, 27)):
        response = context.client.get(reverse("dashboard"))
    page = response.content.decode()
    assert f"{frequency.title()} pass of $25.00 is due in 2 days" in page
    assert f"{frequency.title()}, next due Oct 29, 2026" in page


@when("I record its matching payment on {paid_on}")
def record_payment(context, paid_on):
    context.response = context.client.post(
        reverse("record_expense"),
        {
            "amount": "25.00",
            "date": paid_on,
            "description": context.description,
            "category": "Transportation",
            "is_fixed": "fixed",
            "recurrence": "",
            "next_due_date": "",
        },
    )
    assert context.response.status_code == 302, "The payment was not saved"


@then("its next due date is {due}")
def due_date_advanced(context, due):
    context.schedule.refresh_from_db()
    assert context.schedule.next_due_date == date.fromisoformat(due)
