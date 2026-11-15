"""D14 (#28): recording a fixed expense payment clears its reminder."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class PaymentClearingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = get_user_model().objects.create_user(username="payment-student")
        cls.schedule = Transaction.objects.create(
            owner=cls.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("650.00"),
            date=date(2026, 10, 1),
            description="Rent",
            category="Housing",
            is_fixed=True,
            recurrence=Transaction.Recurrence.MONTHLY,
            next_due_date=date(2026, 11, 1),
        )

    def setUp(self):
        self.client.force_login(self.student)

    @patch("accounts.views.timezone.localdate", return_value=date(2026, 10, 29))
    def test_recording_rent_payment_clears_reminder(self, _today):
        self.assertContains(
            self.client.get(reverse("dashboard")),
            "Rent of $650.00 is due in 3 days",
        )

        response = self.client.post(
            reverse("record_expense"),
            {
                "amount": "650.00",
                "date": "2026-10-29",
                "description": "Rent",
                "category": "Housing",
                "is_fixed": "fixed",
                "recurrence": "",
                "next_due_date": "",
            },
        )

        self.assertRedirects(response, reverse("record_expense"))
        self.assertNotContains(
            self.client.get(reverse("dashboard")),
            "Rent of $650.00 is due",
        )
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.next_due_date, date(2026, 12, 1))
        self.assertEqual(Transaction.objects.filter(owner=self.student).count(), 2)
