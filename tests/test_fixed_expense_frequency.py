"""D14: daily and weekly fixed expense schedules use the same reminder flow."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction
from transactions.views import ExpenseForm


EXPENSE = {
    "amount": "25.00",
    "date": "2026-10-01",
    "description": "Transit pass",
    "category": "Transportation",
    "is_fixed": "fixed",
    "next_due_date": "2026-10-29",
}


class FixedExpenseFrequencyTests(TestCase):
    def setUp(self):
        self.student = get_user_model().objects.create_user(username="frequency-student")
        self.client.force_login(self.student)

    def test_daily_and_weekly_are_valid_schedule_choices(self):
        for frequency in ("daily", "weekly"):
            with self.subTest(frequency=frequency):
                form = ExpenseForm({**EXPENSE, "recurrence": frequency})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["recurrence"], frequency)

    @patch("accounts.views.timezone.localdate", return_value=date(2026, 10, 27))
    def test_daily_and_weekly_schedules_show_upcoming_reminders(self, _today):
        for frequency in ("daily", "weekly"):
            Transaction.objects.create(
                owner=self.student,
                kind=Transaction.Kind.EXPENSE,
                amount="25.00",
                date=date(2026, 10, 1),
                description=f"{frequency.title()} pass",
                category="Transportation",
                is_fixed=True,
                recurrence=frequency,
                next_due_date=date(2026, 10, 29),
            )

        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "Daily pass of $25.00 is due in 2 days")
        self.assertContains(page, "Weekly pass of $25.00 is due in 2 days")

    def test_matching_payments_advance_each_frequency_by_one_period(self):
        for frequency, expected_date in (
            ("daily", date(2026, 10, 30)),
            ("weekly", date(2026, 11, 5)),
        ):
            with self.subTest(frequency=frequency):
                schedule = Transaction.objects.create(
                    owner=self.student,
                    kind=Transaction.Kind.EXPENSE,
                    amount="25.00",
                    date=date(2026, 10, 1),
                    description=f"{frequency.title()} pass",
                    category="Transportation",
                    is_fixed=True,
                    recurrence=frequency,
                    next_due_date=date(2026, 10, 29),
                )

                response = self.client.post(
                    reverse("record_expense"),
                    {
                        **EXPENSE,
                        "description": schedule.description,
                        "date": "2026-10-28",
                        "recurrence": "",
                        "next_due_date": "",
                    },
                )

                self.assertRedirects(response, reverse("record_expense"))
                schedule.refresh_from_db()
                self.assertEqual(schedule.next_due_date, expected_date)
