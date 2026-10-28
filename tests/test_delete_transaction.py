from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class DeleteTransactionTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="deleteuser@example.com",
            email="deleteuser@example.com",
            password="TestPass123!",
        )

        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="TestPass123!",
        )

        self.transaction = Transaction.objects.create(
            owner=self.user,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("40.00"),
            date=date(2026, 10, 28),
            description="Test Textbook",
            category="Books",
            is_fixed=False,
        )

        self.client.force_login(self.user)
        self.url = reverse(
            "delete_transaction",
            args=[self.transaction.pk],
        )

    def test_confirmation_page(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm Delete")
        self.assertTrue(
            Transaction.objects.filter(pk=self.transaction.pk).exists()
        )

    def test_delete_transaction(self):
        response = self.client.post(self.url)

        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(
            Transaction.objects.filter(pk=self.transaction.pk).exists()
        )

    def test_cannot_delete_another_users_transaction(self):
        self.transaction.owner = self.other_user
        self.transaction.save()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Transaction.objects.filter(pk=self.transaction.pk).exists()
        )

    def test_login_required(self):
        self.client.logout()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Transaction.objects.filter(pk=self.transaction.pk).exists()
        )

    def test_cannot_delete_demo_transaction(self):
        self.transaction.is_demo = True
        self.transaction.save()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Transaction.objects.filter(pk=self.transaction.pk).exists()
        )

    def test_nonexistent_transaction_returns_404(self):
        response = self.client.get(
            reverse("delete_transaction", args=[999999])
        )

        self.assertEqual(response.status_code, 404)