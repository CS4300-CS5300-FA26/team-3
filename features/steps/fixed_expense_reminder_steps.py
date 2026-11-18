"""Issue #28 acceptance steps for fixed expense reminders."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from behave import given, then, when


@given('a monthly fixed expense "{description}" of ${amount} is due on {due}')
def scheduled_fixed_expense(context, description, amount, due):
    context.schedule = context.Transaction.objects.create(
        owner=context.student,
        kind=context.Transaction.Kind.EXPENSE,
        amount=Decimal(amount),
        date=date(2026, 10, 1),
        description=description,
        category="Housing",
        is_fixed=True,
        recurrence=context.Transaction.Recurrence.MONTHLY,
        next_due_date=date.fromisoformat(due),
    )


@given("Rent's email notice is set to {days} days")
def set_email_notice(context, days):
    context.schedule.reminder_days = int(days)
    context.schedule.save(update_fields=["reminder_days"])


@given("today is {today} for fixed expense reminders")
def reminder_today(context, today):
    context.today = date.fromisoformat(today)


@when("the daily fixed expense reminder check runs")
def run_daily_check(context):
    from django.core import mail
    from django.core.management import call_command
    from django.test import override_settings

    context.student.email = "reminder-student@example.com"
    context.student.save(update_fields=["email"])
    mail_settings = override_settings(MAILERS={
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    })
    mail_settings.enable()
    context.add_cleanup(mail_settings.disable)

    # Local acceptance runs use in-memory email and refuse any network transport.
    network = patch("socket.socket", side_effect=AssertionError("Unexpected network send"))
    context.network = network.start()
    context.add_cleanup(network.stop)
    call_command("send_fixed_expense_reminders", date=context.today.isoformat())
    context.sent_email = mail.outbox


@then("I receive a Rent reminder email")
def rent_email(context):
    assert len(context.sent_email) == 1
    message = context.sent_email[0]
    assert message.to == [context.student.email]
    assert "Rent" in message.subject and "$650.00" in message.body


@then("no Rent reminder email is sent")
def no_rent_email(context):
    assert not context.sent_email


@then("no text message is sent")
def no_text_message(context):
    assert context.network.call_count == 0, "The check used an external transport"
