"""D-7 (#20): a student's spending per category for one month, ranked."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


def expense(owner, amount, category, day=date(2026, 10, 15), **extra):
    return Transaction.objects.create(
        owner=owner,
        kind=Transaction.Kind.EXPENSE,
        amount=Decimal(amount),
        date=day,
        description=f"{category} purchase",
        category=category,
        **extra,
    )


class SpendingByCategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.student = User.objects.create_user(username="student")
        cls.other = User.objects.create_user(username="other")

        # October 2026: Housing 650.00, Food 120.00 (two entries), Books 60.00.
        expense(cls.student, "650.00", "Housing", date(2026, 10, 1))
        expense(cls.student, "80.00", "Food", date(2026, 10, 3))
        expense(cls.student, "40.00", "Food", date(2026, 10, 31))
        expense(cls.student, "60.00", "Books", date(2026, 10, 20))

        # None of these belong in the student's October breakdown.
        Transaction.objects.create(
            owner=cls.student, kind=Transaction.Kind.INCOME, amount=Decimal("1200.00"),
            date=date(2026, 10, 1), description="Paycheck",
        )
        expense(cls.student, "999.00", "Food", date(2026, 9, 30))
        expense(cls.student, "999.00", "Food", date(2026, 11, 1))
        expense(cls.student, "999.00", "Food", date(2025, 10, 15))
        expense(cls.other, "999.00", "Housing", date(2026, 10, 15))
        expense(None, "999.00", "Food", date(2026, 10, 15), is_demo=True)

    def setUp(self):
        self.client.force_login(self.student)

    def view(self, month="2026-10"):
        return self.client.get(reverse("spending_by_category"), {"month": month})

    def rows(self, response):
        return [(row["category"], row["total"]) for row in response.context["categories"]]

    def test_categories_are_totaled_and_ranked_highest_first(self):
        response = self.view()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.rows(response), [
            ("Housing", Decimal("650.00")),
            ("Food", Decimal("120.00")),
            ("Books", Decimal("60.00")),
        ])

    def test_only_this_students_october_expenses_are_counted(self):
        # Income, other months, the same month last year, another student and
        # demo rows all carry 999.00 or 1200.00, so any leak changes a total.
        totals = dict(self.rows(self.view()))

        self.assertEqual(sum(totals.values()), Decimal("830.00"))

    def test_bars_are_scaled_to_the_largest_category(self):
        response = self.view()
        widths = [row["width"] for row in response.context["categories"]]

        self.assertEqual(widths, ["100.00", "18.46", "9.23"])
        html = response.content.decode()
        self.assertIn('style="width: 100.00%"', html)
        self.assertIn('style="width: 9.23%"', html)

    def test_page_lists_each_category_with_its_total_in_order(self):
        html = self.view().content.decode()

        positions = [html.index(text) for text in (
            "Housing</span>", "$650.00", "Food</span>", "$120.00", "Books</span>", "$60.00",
        )]
        self.assertEqual(positions, sorted(positions))

    def test_equal_totals_are_ordered_by_category_name(self):
        expense(self.student, "25.00", "Transportation", date(2026, 12, 1))
        expense(self.student, "25.00", "Other", date(2026, 12, 2))

        self.assertEqual(
            [category for category, _ in self.rows(self.view("2026-12"))],
            ["Other", "Transportation"],
        )

    def test_month_without_expenses_shows_a_message_and_no_bars(self):
        response = self.view("2027-01")

        self.assertEqual(self.rows(response), [])
        self.assertContains(response, "No expenses in this period")
        self.assertNotContains(response, 'class="bar"')

    @patch("transactions.views.timezone.localdate", return_value=date(2026, 10, 16))
    def test_missing_or_invalid_month_defaults_to_current_month(self, _localdate):
        for month in ["", "invalid", "2026-13", "2026-10-01", "2026-1", "0000-10"]:
            with self.subTest(month=month):
                response = self.view(month)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["selected_month"], "2026-10")
                self.assertEqual(len(response.context["categories"]), 3)

    def test_selected_month_is_kept_in_the_picker(self):
        self.assertContains(self.view("2026-09"), 'value="2026-09"')

    def test_category_text_is_escaped(self):
        expense(self.student, "5.00", "<b>Snacks</b>", date(2026, 8, 1))

        response = self.view("2026-08")

        self.assertContains(response, "&lt;b&gt;Snacks&lt;/b&gt;")
        self.assertNotContains(response, "<b>Snacks</b>")

    def test_signed_out_visitor_is_sent_to_sign_in(self):
        self.client.logout()
        url = reverse("spending_by_category")

        self.assertRedirects(self.client.get(url), reverse("sign_in") + "?next=" + url)

    def test_navigation_links_to_the_breakdown(self):
        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, 'href="' + reverse("spending_by_category") + '"')
