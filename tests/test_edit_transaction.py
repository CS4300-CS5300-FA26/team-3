from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from transactions.models import Transaction


class EditTransactionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="TestPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="TestPass123!",
        )

        self.expense = Transaction.objects.create(
            owner=self.user,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("40.00"),
            date=date(2026, 10, 15),
            description="Textbook",
            category="Books",
            is_fixed=False,
        )

        self.client.force_login(self.user)
        self.url = reverse("edit_transaction", args=[self.expense.pk])

    def test_edit_expense(self):
        response = self.client.post(self.url, {
            "amount": "60.00",
            "date": "2026-10-15",
            "description": "Updated textbook",
            "category": "Books",
            "is_fixed": "variable",
        })

        self.expense.refresh_from_db()

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.expense.amount, Decimal("60.00"))
        self.assertEqual(self.expense.description, "Updated textbook")
        self.assertEqual(self.expense.signed_amount, Decimal("-60.00"))

    def test_edit_preserves_expense_type(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["is_fixed"].value(),
            "variable",
        )

    def test_invalid_amount_is_rejected(self):
        response = self.client.post(self.url, {
            "amount": "0.00",
            "date": "2026-10-15",
            "description": "Textbook",
            "category": "Books",
            "is_fixed": "variable",
        })

        self.assertEqual(response.status_code, 200)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.amount, Decimal("40.00"))

    def test_cannot_edit_another_users_transaction(self):
        self.expense.owner = self.other_user
        self.expense.save()

        response = self.client.post(self.url, {
            "amount": "100.00",
            "date": "2026-10-15",
            "description": "Changed",
            "category": "Books",
            "is_fixed": "variable",
        })

        self.assertEqual(response.status_code, 404)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.amount, Decimal("40.00"))

    def test_login_required(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/sign-in/", response.url)

    def test_cannot_edit_demo_transaction(self):
        self.expense.is_demo = True
        self.expense.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)