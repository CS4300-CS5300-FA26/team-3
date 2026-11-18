"""D14 (#28): the daily check emails upcoming fixed expense reminders."""

from datetime import date
from decimal import Decimal
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.mail import send_mail as django_send_mail
from django.test import TestCase, override_settings
from django.urls import reverse

from transactions.models import Transaction
from transactions.views import ExpenseForm


MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


@override_settings(MAILERS=MAILERS)
class FixedExpenseEmailTests(TestCase):
    def make_schedule(self, name="Rent", reminder_days=3, **changes):
        student = get_user_model().objects.create_user(
            username=f"{name.lower()}-student",
            email=f"{name.lower()}-student@example.com",
        )
        values = {
            "owner": student,
            "kind": Transaction.Kind.EXPENSE,
            "amount": Decimal("650.00"),
            "date": date(2026, 10, 1),
            "description": name,
            "category": "Housing",
            "is_fixed": True,
            "recurrence": Transaction.Recurrence.MONTHLY,
            "next_due_date": date(2026, 11, 1),
            "reminder_days": reminder_days,
        }
        values.update(changes)
        return Transaction.objects.create(**values)

    def test_daily_check_emails_rent_three_days_before_due(self):
        schedule = self.make_schedule()

        call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [schedule.owner.email])
        self.assertIn("Rent", message.subject)
        self.assertIn("$650.00", message.body)
        self.assertIn("November 1, 2026", message.body)

    def test_custom_notice_sends_inside_window_but_not_before_it(self):
        schedule = self.make_schedule(reminder_days=14)

        call_command("send_fixed_expense_reminders", date="2026-10-17")
        self.assertEqual(mail.outbox, [])

        # A missed first day is caught on the next daily run inside the window.
        call_command("send_fixed_expense_reminders", date="2026-10-20")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [schedule.owner.email])

    def test_repeated_daily_check_sends_once_for_one_due_date(self):
        self.make_schedule()

        call_command("send_fixed_expense_reminders", date="2026-10-29")
        call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertEqual(len(mail.outbox), 1)

    def test_edit_loaded_before_email_does_not_erase_delivery_marker(self):
        schedule = self.make_schedule()
        self.client.force_login(schedule.owner)
        original_save = ExpenseForm.save

        def send_reminder_before_edit_save(form, *args, **kwargs):
            call_command("send_fixed_expense_reminders", date="2026-10-29")
            return original_save(form, *args, **kwargs)

        with patch.object(ExpenseForm, "save", send_reminder_before_edit_save):
            response = self.client.post(reverse("edit_transaction", args=[schedule.pk]), {
                "amount": "650.00",
                "date": "2026-10-02",
                "description": "Rent",
                "category": "Housing",
                "is_fixed": "fixed",
                "recurrence": Transaction.Recurrence.MONTHLY,
                "next_due_date": "2026-11-01",
                "reminder_days": "3",
            })

        self.assertEqual(response.status_code, 302)
        schedule.refresh_from_db()
        self.assertEqual(schedule.date, date(2026, 10, 2))
        self.assertEqual(schedule.last_reminded_due_date, date(2026, 11, 1))
        call_command("send_fixed_expense_reminders", date="2026-10-29")
        self.assertEqual(len(mail.outbox), 1)

    def test_description_with_newline_does_not_break_email_subject(self):
        schedule = self.make_schedule()
        schedule.description = "Rent\nNovember"
        schedule.save(update_fields=["description"])

        call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertIn("Rent November", mail.outbox[0].subject)
        self.assertIn("Rent\nNovember", mail.outbox[0].body)
        schedule.refresh_from_db()
        self.assertEqual(schedule.last_reminded_due_date, date(2026, 11, 1))

    def test_new_due_date_gets_its_own_email(self):
        schedule = self.make_schedule()

        call_command("send_fixed_expense_reminders", date="2026-10-29")
        schedule.next_due_date = date(2026, 12, 1)
        schedule.save(update_fields=["next_due_date"])
        call_command("send_fixed_expense_reminders", date="2026-11-28")

        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("November 1, 2026", mail.outbox[0].body)
        self.assertIn("December 1, 2026", mail.outbox[1].body)

    def test_zero_delivery_result_is_retryable(self):
        self.make_schedule()

        with patch(
            "transactions.management.commands.send_fixed_expense_reminders.send_mail",
            return_value=0,
        ):
            with self.assertRaises(CommandError):
                call_command("send_fixed_expense_reminders", date="2026-10-29")
        call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertEqual(len(mail.outbox), 1)

    def test_daily_and_weekly_schedules_email_only_their_owners(self):
        daily = self.make_schedule("Transit", recurrence=Transaction.Recurrence.DAILY)
        weekly = self.make_schedule("Laundry", recurrence=Transaction.Recurrence.WEEKLY)

        call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertCountEqual(
            [message.to for message in mail.outbox],
            [[daily.owner.email], [weekly.owner.email]],
        )

    def test_skips_inactive_demo_unscheduled_and_addressless_expenses(self):
        eligible = self.make_schedule()
        inactive = self.make_schedule("Inactive")
        inactive.owner.is_active = False
        inactive.owner.save(update_fields=["is_active"])
        self.make_schedule("Demo", is_demo=True)
        self.make_schedule("OneTime", recurrence=Transaction.Recurrence.NONE,
                           next_due_date=None)
        addressless = self.make_schedule("Addressless")
        addressless.owner.email = ""
        addressless.owner.save(update_fields=["email"])

        call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [eligible.owner.email])

    def test_failed_email_retries_without_resending_successful_reminders(self):
        successful = self.make_schedule("Rent")
        retry = self.make_schedule("Utilities")
        failed_once = False

        def flaky_send(*args, **kwargs):
            nonlocal failed_once
            if args[3] == [retry.owner.email] and not failed_once:
                failed_once = True
                raise SMTPException("temporary mail failure")
            return django_send_mail(*args, **kwargs)

        with patch(
            "transactions.management.commands.send_fixed_expense_reminders.send_mail",
            side_effect=flaky_send,
        ):
            with self.assertRaises(CommandError):
                call_command("send_fixed_expense_reminders", date="2026-10-29")
            call_command("send_fixed_expense_reminders", date="2026-10-29")

        self.assertEqual(len(mail.outbox), 2)
        self.assertCountEqual(
            [message.to for message in mail.outbox],
            [[successful.owner.email], [retry.owner.email]],
        )
