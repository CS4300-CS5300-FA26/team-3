from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from transactions.models import Transaction
from transactions.views import IncomeForm


class IncomeFormTests(TestCase):
    def test_accepts_paycheck_details_as_exact_money(self):
        form = IncomeForm(
            {"amount": "1200.00", "date": "2026-10-02", "description": "Part-time job"}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], Decimal("1200.00"))
        self.assertEqual(form.cleaned_data["date"], date(2026, 10, 2))
        self.assertEqual(form.cleaned_data["description"], "Part-time job")

    def test_rejects_zero_amount_with_story_message(self):
        form = IncomeForm(
            {"amount": "0.00", "date": "2026-10-02", "description": "Part-time job"}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Amount must be greater than zero", form.errors["amount"])


class RecordIncomeViewTests(TestCase):
    def test_post_without_csrf_token_is_rejected_without_saving(self):
        student = get_user_model().objects.create_user(username="student")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(student)

        response = csrf_client.post(
            reverse("record_income"),
            {"amount": "5.00", "date": "2026-10-20", "description": "CSRF attempt"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Transaction.objects.filter(description="CSRF attempt").exists())

    def test_post_cannot_override_income_kind(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        self.client.post(
            reverse("record_income"),
            {
                "amount": "5.00",
                "date": "2026-10-20",
                "description": "Kind override attempt",
                "kind": "expense",
                "category": "Food",
            },
        )

        income = Transaction.objects.get(description="Kind override attempt")
        self.assertEqual(income.kind, Transaction.Kind.INCOME)
        self.assertEqual(income.category, "")

    def test_post_cannot_mark_income_as_demo(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        self.client.post(
            reverse("record_income"),
            {
                "amount": "5.00",
                "date": "2026-10-20",
                "description": "Demo override attempt",
                "is_demo": "on",
            },
        )

        income = Transaction.objects.get(description="Demo override attempt")
        self.assertFalse(income.is_demo)

    def test_anonymous_post_redirects_without_saving_income(self):
        response = self.client.post(
            reverse("record_income"),
            {"amount": "5.00", "date": "2026-10-20", "description": "Anonymous attempt"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Transaction.objects.filter(description="Anonymous attempt").exists()
        )

    def test_signed_in_student_can_open_income_form(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.get(reverse("record_income"))

        self.assertContains(response, "Source")

    def test_submitting_paycheck_saves_an_income_transaction(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.post(
            reverse("record_income"),
            {"amount": "1200.00", "date": "2026-10-02", "description": "Part-time job"},
            follow=True,
        )

        income = Transaction.objects.get(description="Part-time job", is_demo=False)
        self.assertEqual(income.kind, Transaction.Kind.INCOME)
        self.assertEqual(income.amount, Decimal("1200.00"))
        self.assertEqual(income.date, date(2026, 10, 2))
        self.assertEqual(income.owner, student)
        self.assertContains(response, "Income saved.")

    def test_zero_amount_post_shows_error_and_saves_nothing(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.post(
            reverse("record_income"),
            {"amount": "0.00", "date": "2026-10-02", "description": "Invalid paycheck"},
        )

        self.assertContains(response, "Amount must be greater than zero")
        self.assertFalse(
            Transaction.objects.filter(description="Invalid paycheck", is_demo=False).exists()
        )

    def test_negative_amount_post_shows_error_and_saves_nothing(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.post(
            reverse("record_income"),
            {"amount": "-0.01", "date": "2026-10-02", "description": "Negative paycheck"},
        )

        self.assertContains(response, "Amount must be greater than zero")
        self.assertFalse(
            Transaction.objects.filter(description="Negative paycheck", is_demo=False).exists()
        )

    def test_missing_source_shows_error_and_saves_nothing(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.post(
            reverse("record_income"),
            {"amount": "1200.00", "date": "2026-10-02", "description": ""},
        )

        self.assertContains(response, "Enter an income source.")
        self.assertFalse(Transaction.objects.filter(is_demo=False).exists())


class TransactionListViewTests(TestCase):
    def setUp(self):
        """Start each view test with an empty transaction table and a session."""
        Transaction.objects.all().delete()
        self.client.force_login(get_user_model().objects.create_user(username="list-student"))

    def test_transaction_list_returns_success(self):
        """The transaction landing page should be accessible."""
        response = self.client.get(reverse("transaction_list"))

        self.assertEqual(response.status_code, 200)

    def test_transaction_list_displays_empty_state(self):
        """The landing page should handle an empty transaction database."""
        response = self.client.get(reverse("transaction_list"))

        self.assertContains(response, "No transactions in this period")

    def test_transaction_list_displays_demo_transaction(self):
        """The legacy demo page still renders its synthetic rows until D2 replaces it."""
        Transaction.objects.create(
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("25.50"),
            date=date(2026, 10, 5),
            description="Demo Lunch",
            category="Food",
            is_demo=True,
        )

        response = self.client.get(reverse("transaction_list"), {"month": "2026-10"})

        self.assertContains(response, "Demo Lunch")
        self.assertContains(response, "Food")
        self.assertContains(response, "25.50")

    def test_transaction_list_hides_non_demo_transaction(self):
        """The legacy demo page must not expose private transactions."""
        Transaction.objects.create(
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("99.99"),
            date=date(2026, 10, 5),
            description="Private Transaction",
            category="Personal",
        )

        response = self.client.get(reverse("transaction_list"), {"month": "2026-10"})

        self.assertNotContains(response, "Private Transaction")
        self.assertNotContains(response, "99.99")
