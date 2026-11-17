"""D14 (#28): reminders for upcoming recurring fixed expenses."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class DashboardReminderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = get_user_model().objects.create_user(username="reminder-student")
        Transaction.objects.create(
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
    def test_rent_due_in_three_days_appears_on_dashboard(self, _today):
        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Rent of $650.00 is due in 3 days")

    @patch("accounts.views.timezone.localdate", return_value=date(2026, 10, 20))
    def test_rent_due_later_does_not_appear_on_dashboard(self, _today):
        response = self.client.get(reverse("dashboard"))

        self.assertNotContains(response, "Rent of $650.00 is due")

