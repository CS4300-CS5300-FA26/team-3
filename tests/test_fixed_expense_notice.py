"""D14 (#28): students can choose when a fixed expense reminder appears."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction
from transactions.views import ExpenseForm


RENT = {
    "amount": "650.00",
    "date": "2026-10-01",
    "description": "Rent",
    "category": "Housing",
    "is_fixed": "fixed",
    "recurrence": "monthly",
    "next_due_date": "2026-11-01",
}


class FixedExpenseNoticeTests(TestCase):
    def setUp(self):
        self.student = get_user_model().objects.create_user(username="notice-student")
        self.client.force_login(self.student)

    @patch("accounts.views.timezone.localdate", return_value=date(2026, 10, 20))
    def test_custom_14_day_notice_shows_rent_twelve_days_early(self, _today):
        response = self.client.post(
            reverse("record_expense"), {**RENT, "reminder_days": "14"}
        )

        self.assertRedirects(response, reverse("record_expense"))
        self.assertEqual(
            Transaction.objects.get(owner=self.student).reminder_days, 14
        )
        self.assertContains(
            self.client.get(reverse("dashboard")),
            "Rent of $650.00 is due in 12 days",
        )

    def test_30_days_is_allowed(self):
        form = ExpenseForm({**RENT, "reminder_days": "30"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["reminder_days"], 30)

    def test_more_than_30_days_is_rejected(self):
        form = ExpenseForm({**RENT, "reminder_days": "31"})

        self.assertFalse(form.is_valid())
        self.assertIn("reminder_days", form.errors)

    def test_invalid_notice_keeps_the_saved_30_day_setting(self):
        schedule = Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount="650.00",
            date=date(2026, 10, 1),
            description="Rent",
            category="Housing",
            is_fixed=True,
            recurrence=Transaction.Recurrence.MONTHLY,
            next_due_date=date(2026, 11, 1),
            reminder_days=30,
        )

        response = self.client.post(
            reverse("edit_transaction", args=[schedule.pk]),
            {**RENT, "reminder_days": "31"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reminder_days", response.context["form"].errors)
        schedule.refresh_from_db()
        self.assertEqual(schedule.reminder_days, 30)

    @patch("accounts.views.timezone.localdate", return_value=date(2026, 10, 20))
    def test_matching_payment_clears_a_custom_14_day_reminder(self, _today):
        schedule = Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount="650.00",
            date=date(2026, 10, 1),
            description="Rent",
            category="Housing",
            is_fixed=True,
            recurrence=Transaction.Recurrence.MONTHLY,
            next_due_date=date(2026, 11, 1),
            reminder_days=14,
        )
        self.assertContains(
            self.client.get(reverse("dashboard")),
            "Rent of $650.00 is due in 12 days",
        )

        response = self.client.post(
            reverse("record_expense"),
            {
                **RENT,
                "date": "2026-10-20",
                "recurrence": "",
                "next_due_date": "",
            },
        )

        self.assertRedirects(response, reverse("record_expense"))
        schedule.refresh_from_db()
        self.assertEqual(schedule.next_due_date, date(2026, 12, 1))
        self.assertNotContains(
            self.client.get(reverse("dashboard")), "Rent of $650.00 is due"
        )
