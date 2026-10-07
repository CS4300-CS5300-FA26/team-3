from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class TransactionListViewTests(TestCase):
    def setUp(self):
        """Start each view test with an empty transaction table."""
        Transaction.objects.all().delete()

    def test_transaction_list_returns_success(self):
        """The transaction landing page should be accessible."""
        response = self.client.get(reverse("transaction_list"))

        self.assertEqual(response.status_code, 200)

    def test_transaction_list_displays_empty_state(self):
        """The landing page should handle an empty transaction database."""
        response = self.client.get(reverse("transaction_list"))

        self.assertContains(response, "No transactions yet.")

    def test_transaction_list_displays_demo_transaction(self):
        """Demo transactions stored in the database should appear publicly."""
        Transaction.objects.create(
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("25.50"),
            date=date(2026, 10, 5),
            description="Demo Lunch",
            category="Food",
            is_demo=True,
        )

        response = self.client.get(reverse("transaction_list"))

        self.assertContains(response, "Demo Lunch")
        self.assertContains(response, "Food")
        self.assertContains(response, "25.50")

    def test_transaction_list_hides_non_demo_transaction(self):
        """Non-demo transactions should not appear on the public landing page."""
        Transaction.objects.create(
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("99.99"),
            date=date(2026, 10, 5),
            description="Private Transaction",
            category="Personal",
        )

        response = self.client.get(reverse("transaction_list"))

        self.assertNotContains(response, "Private Transaction")
        self.assertNotContains(response, "99.99")