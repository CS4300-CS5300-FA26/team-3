"""Issue #25 recurrence checks. Shared steps are in common_steps.py."""

from datetime import date

from behave import given, then, when

from common_steps import money

EXPENSE_DATE = "2026-10-01"


@given('I am adding an expense of ${amount} for "{description}" marked as {kind}')
def expense_in_progress(context, amount, description, kind):
    context.expense = {
        "amount": money(amount),
        "date": EXPENSE_DATE,
        "description": description,
        "category": "Housing",
        "is_fixed": kind.lower(),
    }


@when("I save it with a monthly recurrence and next due date of {due}")
def save_with_schedule(context, due):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("record_expense"),
        {**context.expense, "recurrence": "monthly", "next_due_date": due},
    )
    assert context.response.status_code == 302, "The expense was not saved"


@then('"{description}" shows a next due date of {due}')
def shows_next_due_date(context, description, due):
    from django.urls import reverse

    saved = context.Transaction.objects.get(owner=context.student, description=description)
    assert saved.next_due_date == date.fromisoformat(due)

    dashboard = context.client.get(reverse("dashboard"), {"month": EXPENSE_DATE[:7]})
    shown = f"Monthly, next due {date.fromisoformat(due):%b} {date.fromisoformat(due).day}, {due[:4]}"
    assert shown in dashboard.content.decode(), f"Expected {shown!r} on the dashboard"


@when("I view recurrence scheduling")
def view_scheduling(context):
    # Save the variable expense with a schedule attempt, as a leftover or edited
    # request would send it, then open the saved expense's edit form.
    from django.urls import reverse

    context.client.post(
        reverse("record_expense"),
        {**context.expense, "recurrence": "monthly", "next_due_date": "2026-11-01"},
    )
    context.saved = context.Transaction.objects.get(
        owner=context.student, description=context.expense["description"]
    )
    context.response = context.client.get(reverse("edit_transaction", args=[context.saved.pk]))


@then("no recurrence schedule is offered")
def no_schedule_offered(context):
    assert context.saved.recurrence == "" and context.saved.next_due_date is None
    assert 'id="recurrence-fields" hidden disabled' in context.response.content.decode()
