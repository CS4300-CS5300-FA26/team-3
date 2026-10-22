from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class RemainingBudgetViewTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username="budget-student"))

    @classmethod
    def setUpTestData(cls):
        # Replace seeded demo data with predictable acceptance-test examples.
        Transaction.objects.all().delete()
        rows = [
            ("income", "1200.00", date(2026, 10, 1), "October pay", ""),
            ("expense", "650.00", date(2026, 10, 2), "October rent", "Housing"),
            ("expense", "120.00", date(2026, 10, 15), "October groceries", "Food"),
            ("expense", "60.00", date(2026, 10, 31), "October textbook", "Books"),
            ("income", "500.00", date(2026, 9, 30), "September pay", ""),
            ("expense", "50.00", date(2026, 11, 1), "November groceries", "Food"),
            ("income", "900.00", date(2025, 10, 1), "Previous October pay", ""),
        ]
        for kind, amount, transaction_date, description, category in rows:
            Transaction.objects.create(
                kind=kind,
                amount=Decimal(amount),
                date=transaction_date,
                description=description,
                category=category,
                is_demo=True,
            )

        # The current public dashboard must exclude private data from totals too.
        Transaction.objects.create(
            kind=Transaction.Kind.INCOME,
            amount=Decimal("100.00"),
            date=date(2026, 10, 10),
            description="Private pay",
            is_demo=False,
        )

    def test_october_displays_remaining_budget_for_selected_month(self):
        response = self.client.get(
            reverse("transaction_list"), {"month": "2026-10"}
        )

        self.assertContains(response, "Remaining budget")
        self.assertContains(response, "$370.00")
        self.assertEqual(response.context["remaining_budget"], Decimal("370.00"))
        self.assertContains(response, "October pay")
        self.assertContains(response, "October textbook")
        self.assertNotContains(response, "September pay")
        self.assertNotContains(response, "November groceries")
        self.assertNotContains(response, "Previous October pay")
        self.assertNotContains(response, "Private pay")
        self.assertNotContains(response, "No transactions in this period")

    def test_december_displays_zero_and_empty_period_message(self):
        response = self.client.get(
            reverse("transaction_list"), {"month": "2026-12"}
        )

        self.assertContains(response, "Remaining budget")
        self.assertContains(response, "$0.00")
        self.assertContains(response, "No transactions in this period")
        self.assertEqual(response.context["remaining_budget"], Decimal("0.00"))
        self.assertQuerySetEqual(response.context["transactions"], [])

    def test_view_calculates_selected_period_before_rendering(self):
        for month, expected, count in [
            ("2026-10", Decimal("370.00"), 4),
            ("2026-12", Decimal("0.00"), 0),
            ("2026-11", Decimal("-50.00"), 1),
            ("2025-10", Decimal("900.00"), 1),
        ]:
            with self.subTest(month=month):
                response = self.client.get(
                    reverse("transaction_list"), {"month": month}
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["remaining_budget"], expected)
                self.assertEqual(response.context["selected_month"], month)
                self.assertEqual(len(response.context["transactions"]), count)

    @patch("transactions.views.timezone.localdate", return_value=date(2026, 10, 16))
    def test_missing_or_invalid_month_defaults_to_current_month(self, _localdate):
        for params in [
            {},
            {"month": ""},
            {"month": "invalid"},
            {"month": "2026-13"},
            {"month": "2026-10-01"},
            {"month": "0000-10"},
        ]:
            with self.subTest(params=params):
                response = self.client.get(reverse("transaction_list"), params)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["selected_month"], "2026-10")
                self.assertEqual(
                    response.context["remaining_budget"], Decimal("370.00")
                )
