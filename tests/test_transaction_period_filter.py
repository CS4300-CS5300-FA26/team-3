from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import LowBalanceThreshold
from transactions.models import Transaction


class TransactionPeriodFilterTests(TestCase):
    today = date(2026, 11, 15)

    def setUp(self):
        self.student = get_user_model().objects.create_user(username="period-student")
        self.other_student = get_user_model().objects.create_user(username="period-other")
        self.client.force_login(self.student)

    def create_transaction(self, kind, amount, transaction_date, description, owner=None, is_demo=False):
        return Transaction.objects.create(
            kind=kind,
            amount=Decimal(amount),
            date=transaction_date,
            description=description,
            owner=owner or self.student,
            is_demo=is_demo,
            category="Food" if kind == Transaction.Kind.EXPENSE else "",
        )

    def get_dashboard(self, period):
        with patch("accounts.views.timezone.localdate", return_value=self.today):
            return self.client.get(reverse("dashboard"), {"period": period})

    def test_period_selector_submits_after_its_markup_is_loaded(self):
        response = self.get_dashboard("selected_month")
        content = response.content.decode()

        self.assertIn('data-auto-submit="period"', content)
        self.assertIn('document.addEventListener("change"', content)

    def test_selected_date_range_is_displayed_next_to_period_selector(self):
        self.create_transaction(
            Transaction.Kind.INCOME, "10.00", date(2026, 10, 1), "Oldest transaction"
        )
        self.create_transaction(
            Transaction.Kind.INCOME, "15.00", date(2026, 11, 15), "Newest transaction"
        )

        expected_ranges = {
            "selected_month": "Nov 1, 2026 – Nov 30, 2026",
            "last_3_days": "Nov 13, 2026 – Nov 15, 2026",
            "last_7_days": "Nov 9, 2026 – Nov 15, 2026",
            "last_14_days": "Nov 2, 2026 – Nov 15, 2026",
            "this_month": "Nov 1, 2026 – Nov 15, 2026",
            "this_quarter": "Oct 1, 2026 – Nov 15, 2026",
            "all": "Oct 1, 2026 – Nov 15, 2026",
        }
        for period, expected in expected_ranges.items():
            with self.subTest(period=period):
                response = self.get_dashboard(period)
                self.assertContains(response, expected)

    def test_preset_ranges_include_the_start_and_today(self):
        rows = [
            ("last_3_days", date(2026, 11, 13), "Last 3 start"),
            ("last_3_days", date(2026, 11, 12), "Before last 3"),
            ("last_7_days", date(2026, 11, 9), "Last 7 start"),
            ("last_7_days", date(2026, 11, 8), "Before last 7"),
            ("last_14_days", date(2026, 11, 2), "Last 14 start"),
            ("last_14_days", date(2026, 11, 1), "Before last 14"),
            ("this_month", date(2026, 11, 1), "Month start"),
            ("this_month", date(2026, 10, 31), "Before this month"),
            ("this_quarter", date(2026, 10, 1), "Quarter start"),
            ("this_quarter", date(2026, 9, 30), "Before this quarter"),
            ("all", self.today, "Today"),
        ]
        for _, transaction_date, description in rows:
            self.create_transaction(
                Transaction.Kind.INCOME, "1.00", transaction_date, description
            )

        expected_by_period = {
            "last_3_days": {"Last 3 start", "Today"},
            "last_7_days": {"Before last 3", "Last 7 start", "Last 3 start", "Today"},
            "last_14_days": {
                "Before last 3", "Last 7 start", "Before last 7", "Last 14 start",
                "Last 3 start", "Today",
            },
            "this_month": {
                "Before last 3", "Last 7 start", "Before last 7", "Last 14 start",
                "Before last 14", "Month start", "Last 3 start", "Today",
            },
            "this_quarter": {
                "Before last 3", "Last 7 start", "Before last 7", "Last 14 start",
                "Before last 14", "Month start", "Before this month", "Quarter start",
                "Last 3 start", "Today",
            },
        }
        excluded_by_period = {
            "last_3_days": {"Before last 3", "Last 7 start", "Before last 7", "Last 14 start",
                             "Before last 14", "Month start", "Before this month", "Quarter start",
                             "Before this quarter"},
            "last_7_days": {"Before last 7", "Last 14 start", "Before last 14", "Month start",
                             "Before this month", "Quarter start", "Before this quarter"},
            "last_14_days": {"Before last 14", "Month start", "Before this month", "Quarter start",
                              "Before this quarter"},
            "this_month": {"Before this month", "Quarter start", "Before this quarter"},
            "this_quarter": {"Before this quarter"},
        }
        for period, expected in expected_by_period.items():
            with self.subTest(period=period):
                response = self.get_dashboard(period)
                descriptions = {
                    transaction.description for transaction in response.context["transactions"]
                }
                self.assertTrue(expected.issubset(descriptions))
                self.assertFalse(excluded_by_period[period] & descriptions)

    def test_period_totals_do_not_change_monthly_budget_or_warning(self):
        self.create_transaction(
            Transaction.Kind.INCOME, "200.00", date(2026, 11, 15), "Selected income"
        )
        self.create_transaction(
            Transaction.Kind.EXPENSE, "42.50", date(2026, 11, 14), "Selected expense"
        )
        self.create_transaction(
            Transaction.Kind.EXPENSE, "100.00", date(2026, 11, 1), "Outside period expense"
        )
        LowBalanceThreshold.objects.create(owner=self.student, amount=Decimal("60.00"))

        response = self.get_dashboard("last_3_days")

        self.assertEqual(response.context["income_total"], Decimal("200.00"))
        self.assertEqual(response.context["expense_total"], Decimal("42.50"))
        self.assertEqual(response.context["remaining_budget"], Decimal("57.50"))
        self.assertTrue(response.context["show_low_balance_warning"])
        self.assertNotContains(response, "Outside period expense")

    def test_empty_period_shows_message_and_zero_totals(self):
        self.create_transaction(
            Transaction.Kind.INCOME, "75.00", date(2026, 10, 1), "Older income"
        )

        response = self.get_dashboard("last_3_days")

        self.assertContains(response, "No transactions in this period")
        self.assertEqual(response.context["income_total"], Decimal("0.00"))
        self.assertEqual(response.context["expense_total"], Decimal("0.00"))

    def test_all_time_restores_all_personal_transactions_and_totals(self):
        self.create_transaction(
            Transaction.Kind.INCOME, "200.00", date(2026, 11, 15), "Recent income"
        )
        self.create_transaction(
            Transaction.Kind.EXPENSE, "42.50", date(2026, 1, 10), "Older expense"
        )
        self.create_transaction(
            Transaction.Kind.INCOME, "999.00", date(2026, 11, 15), "Other income",
            owner=self.other_student,
        )
        self.create_transaction(
            Transaction.Kind.INCOME, "888.00", date(2026, 11, 15), "Demo income",
            is_demo=True,
        )

        response = self.get_dashboard("all")

        descriptions = {item.description for item in response.context["transactions"]}
        self.assertEqual(descriptions, {"Recent income", "Older expense"})
        self.assertEqual(response.context["income_total"], Decimal("200.00"))
        self.assertEqual(response.context["expense_total"], Decimal("42.50"))
