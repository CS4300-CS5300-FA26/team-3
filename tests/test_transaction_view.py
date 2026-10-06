from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class TransactionListViewTests(TestCase):
    def test_transaction_list_returns_success(self):
        """The transaction landing page should be accessible."""
        response = self.client.get(reverse("transaction_list"))

        self.assertEqual(response.status_code, 200)

    def test_transaction_list_displays_empty_state(self):
        """The landing page should handle an empty transaction database."""
        response = self.client.get(reverse("transaction_list"))

        self.assertContains(response, "No transactions yet.")

    def test_transaction_list_displays_database_transaction(self):
        """Transactions stored in the database should appear on the landing page."""
        Transaction.objects.create(
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("25.50"),
            date=date(2026, 10, 5),
            description="Lunch",
            category="Food",
        )

        response = self.client.get(reverse("transaction_list"))

        self.assertContains(response, "Lunch")
        self.assertContains(response, "Food")
        self.assertContains(response, "25.50")