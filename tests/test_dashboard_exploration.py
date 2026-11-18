"""#74: monthly figures, honest chart cutoffs, and URL-backed exploration."""
from datetime import date
from decimal import Decimal
from html import unescape
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class DashboardExplorationTests(TestCase):
    today = date(2026, 11, 16)

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="explorer")
        self.other = get_user_model().objects.create_user(username="other-explorer")
        self.client.force_login(self.user)

    def entry(self, amount, day, category="Food", kind="expense", **kwargs):
        return Transaction.objects.create(
            owner=kwargs.pop("owner", self.user), amount=amount, date=day,
            category=category if kind == "expense" else "", kind=kind,
            description=kwargs.pop("description", f"{day} {category}"), **kwargs,
        )

    def dashboard(self, **params):
        with patch("accounts.views.timezone.localdate", return_value=self.today):
            return self.client.get(reverse("dashboard"), {"month": "2026-11", **params})

    def test_monthly_money_categories_and_daily_points_are_exact_and_private(self):
        self.entry("10.00", "2026-11-01", kind="income")
        self.entry("0.10", "2026-11-01")
        self.entry("0.20", "2026-11-01")
        self.entry("0.30", "2026-11-03", "Books")
        self.entry("90.00", "2026-11-02", owner=self.other)
        self.entry("80.00", "2026-11-02", is_demo=True)
        self.entry("70.00", "2025-11-01")
        response = self.dashboard(period="last_3_days")
        self.assertEqual(response.context["monthly_income"], Decimal("10.00"))
        self.assertEqual(response.context["monthly_expenses"], Decimal("0.60"))
        self.assertEqual(response.context["remaining_budget"], Decimal("9.40"))
        categories = response.context["categories"]
        self.assertEqual([r["category"] for r in categories], ["Books", "Food"])
        self.assertEqual([(r["width"], r["share"]) for r in categories], [("100.00", "50.00")] * 2)
        points = response.context["spending_days"]
        self.assertEqual(len(points), 16)
        self.assertEqual([p["total"] for p in points[:3]], [Decimal(".30"), Decimal(".30"), Decimal(".60")])
        self.assertEqual(points[1]["amount"], Decimal("0"))
        self.assertEqual(response.context["expense_total"], Decimal("0"))
        self.assertContains(response, "Filtered history totals")
        self.assertNotContains(response, "Bars compare with the largest category")

    @patch("accounts.views.generate_spending_summary")
    def test_explanation_keeps_exact_totals_after_dashboard_exploration(self, generate_summary):
        for amount in ("0.10", "0.20") * 5:
            self.entry(amount, "2026-11-01")
        self.entry("99", "2026-11-01", owner=self.other)
        self.entry("88", "2026-11-01", is_demo=True)
        self.entry("77", "2026-10-01")
        generate_summary.return_value = ["Food totaled $1.50."]
        response = self.client.post(reverse("explain_spending"), {
            "month": "2026-11", "period": "selected_month", "explain_spending": "1",
        })
        self.assertContains(response, "Food totaled $1.50.")
        generate_summary.assert_called_once_with([
            {"category": "Food", "total": Decimal("1.50"), "count": 10},
        ])
        self.assertEqual(response.context["monthly_expenses"], Decimal("1.50"))

    @patch("accounts.views.generate_spending_summary")
    def test_explanation_form_preserves_active_filters(self, generate_summary):
        wanted = [self.entry("0.10", "2026-11-03", "Food & drink") for _ in range(10)]
        self.entry("20", "2026-11-04", "Food & drink")
        self.entry("30", "2026-11-03", "Books")
        self.entry("40", "2026-11-03", kind="income")
        self.entry("50", "2026-11-03", "Food & drink", owner=self.other)
        self.entry("60", "2026-11-03", "Food & drink", is_demo=True)
        generate_summary.return_value = ["Food & drink totaled $1.00."]
        page = self.dashboard(kind="expense", category="Food & drink", date="2026-11-03")
        action = unescape(re.search(
            rf'<form method="post" action="({reverse("explain_spending")}[^"]*)"', page.content.decode(),
        ).group(1))
        response = self.client.post(action, {
            "month": "2026-11", "period": "selected_month", "explain_spending": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context["transactions"]), set(wanted))
        self.assertEqual(response.context["drilldown_filters"], page.context["drilldown_filters"])
        self.assertEqual(response.context["period_start"], date(2026, 11, 3))
        self.assertEqual(response.context["period_end"], date(2026, 11, 3))
        self.assertEqual(response.context["expense_total"], Decimal("1.00"))
        self.assertEqual(response.context["monthly_expenses"], Decimal("51.00"))
        generate_summary.assert_called_once_with([
            {"category": "Food & drink", "total": Decimal("1.00"), "count": 10},
        ])
        self.assertContains(response, "Food &amp; drink totaled $1.00.")

    def test_dashboard_omits_repeated_explanations_but_keeps_period_controls(self):
        response = self.dashboard()
        for text in ("Income minus expenses for this month", "History: Selected month", "all recorded expenses"):
            self.assertNotContains(response, text)
        self.assertContains(response, 'id="period"')
        self.assertContains(response, "Nov 1, 2026 – Nov 30, 2026")
        self.assertNotContains(response, "future-dated expenses.")

    def test_upcoming_expenses_have_labeled_columns(self):
        self.entry("60", "2026-10-18", "Other", description="Internet", is_fixed=True,
                   recurrence="monthly", next_due_date="2026-11-18")
        response = self.dashboard()
        for label in ("Expense", "Amount", "Due"):
            self.assertContains(response, f'<th scope="col">{label}</th>', html=True)
        self.assertContains(response, "Internet of $60.00 is due in 2 days")

    def test_spending_details_distinguish_comparison_width_from_share(self):
        self.entry("1.00", "2026-11-01", "Food")
        self.entry("3.00", "2026-11-01", "Books")
        response = self.client.get(reverse("spending_by_category"), {"month": "2026-11"})
        self.assertContains(response, "25.00% of total spending")
        self.assertContains(response, "75.00% of total spending")
        self.assertContains(response, "Bars compare with the largest category")

    def test_cutoff_keeps_future_records_in_budget_without_warning(self):
        self.entry("10.25", "2026-11-16")
        self.entry("20.50", "2026-11-30")
        response = self.dashboard()
        self.assertEqual(response.context["monthly_expenses"], Decimal("30.75"))
        self.assertEqual(response.context["chart_total"], Decimal("10.25"))
        self.assertEqual(response.context["future_expenses"], Decimal("20.50"))
        self.assertNotContains(response, "future-dated expenses.")
        self.assertContains(response, "through Nov 16")

    def test_current_month_with_only_future_expenses_is_honest(self):
        self.entry("10.00", "2026-11-30")
        response = self.dashboard()
        self.assertEqual(response.context["chart_total"], Decimal("0"))
        self.assertContains(response, "No spending to date")
        self.assertNotContains(response, "future-dated expenses.")

    def test_complete_past_months_leap_year_and_year_boundaries(self):
        for month, length in [("2024-02", 29), ("2025-02", 28), ("2025-12", 31), ("2026-01", 31)]:
            with self.subTest(month=month):
                self.entry("12.34", f"{month}-{length}")
                response = self.dashboard(month=month)
                points = response.context["spending_days"]
                self.assertEqual(len(points), length)
                self.assertEqual(points[-1]["date"].isoformat(), f"{month}-{length}")
                self.assertEqual(points[-1]["total"], Decimal("12.34"))
                self.assertEqual(points[0]["total"], Decimal("0"))

    def test_future_month_has_no_fake_chart_but_keeps_recorded_totals(self):
        self.entry("5.00", "2027-01-01")
        response = self.dashboard(month="2027-01")
        self.assertEqual(response.context["spending_days"], [])
        self.assertEqual(response.context["monthly_expenses"], Decimal("5"))
        self.assertContains(response, "No spending to date")
        self.assertContains(response, "This month has not started")

    def test_empty_current_month_and_first_day_have_zero_points(self):
        self.today = date(2026, 11, 1)
        response = self.dashboard()
        self.assertEqual(len(response.context["spending_days"]), 1)
        self.assertEqual(response.context["chart_total"], Decimal("0"))
        self.assertContains(response, "No expenses in this month")
        self.assertNotContains(response, "Filtered history totals")

    def test_drilldowns_use_month_not_independent_history_and_remove_individually(self):
        wanted = self.entry("0.30", "2026-11-03", "Food & drink")
        self.entry("2", "2026-11-04", "Food & drink")
        self.entry("3", "2026-10-03", "Food & drink")
        self.entry("4", "2026-11-03", "Books")
        self.entry("5", "2026-11-03", kind="income")
        response = self.dashboard(period="all")
        category = next(r for r in response.context["categories"] if r["category"] == "Food & drink")
        params = parse_qs(urlsplit(category["url"]).query)
        self.assertEqual(params["period"], ["selected_month"])
        self.assertEqual(params["category"], ["Food & drink"])
        with patch("accounts.views.timezone.localdate", return_value=self.today):
            clicked = self.client.get(category["url"])
        self.assertEqual(len(clicked.context["transactions"]), 2)
        response = self.dashboard(kind="expense", category="Food & drink", date="2026-11-03")
        self.assertEqual(list(response.context["transactions"]), [wanted])
        filters = {f["key"]: f for f in response.context["drilldown_filters"]}
        removed = self.client.get(filters["category"]["url"])
        self.assertEqual(len(removed.context["transactions"]), 2)
        self.assertContains(response, "Clear filters")
        cleared = self.client.get(response.context["clear_filters_url"])
        self.assertEqual(len(cleared.context["transactions"]), 4)

    def test_income_and_chart_day_links_select_correct_month_and_kind(self):
        income = self.entry("20", "2026-11-02", kind="income")
        expense = self.entry("1", "2026-11-02")
        response = self.dashboard(period="all")
        income_response = self.client.get(response.context["income_url"])
        self.assertEqual(list(income_response.context["transactions"]), [income])
        point = response.context["spending_days"][1]
        day_response = self.client.get(point["url"])
        self.assertEqual(list(day_response.context["transactions"]), [expense])
        self.assertEqual(day_response.context["period_start"], date(2026, 11, 2))
        self.assertEqual(day_response.context["period_end"], date(2026, 11, 2))

    def test_presets_ignore_stale_criteria_and_invalid_filters_are_safe(self):
        income = self.entry("20", "2026-11-16", kind="income")
        old = self.entry("1", "2026-10-02")
        response = self.dashboard(period="all", kind="expense", category="Missing", date="2026-10-02")
        self.assertEqual(set(response.context["transactions"]), {income, old})
        self.assertEqual(response.context["drilldown_filters"], [])
        for params in [dict(kind="bad", date="bad"), dict(date="2026-10-02"), dict(date="20261116"), dict(category="x" * 51)]:
            with self.subTest(params=params):
                response = self.dashboard(**params)
                self.assertEqual(list(response.context["transactions"]), [income])
                self.assertEqual(response.context["drilldown_filters"], [])
        self.assertEqual(len(self.dashboard(category="Missing").context["transactions"]), 0)

    def test_scope_equality_does_not_duplicate_totals_at_month_end(self):
        self.today = date(2026, 11, 30)
        self.assertNotContains(self.dashboard(period="this_month"), "Filtered history totals")
        self.assertContains(self.dashboard(period="this_month", month="2026-10"), "Filtered history totals")
        self.assertContains(self.dashboard(kind="expense"), "Filtered history totals")

    def test_category_is_escaped_and_url_encoded(self):
        self.entry("1", "2026-11-01", "<script>&other=1")
        response = self.dashboard()
        self.assertContains(response, "&lt;script&gt;&amp;other=1")
        self.assertNotContains(response, "<script>&other=1")
        self.assertIn("%3Cscript%3E%26other%3D1", response.context["categories"][0]["url"])
