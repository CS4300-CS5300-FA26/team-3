from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from transactions.models import Transaction
from transactions.views import ExpenseForm

RENT = {
    "amount": "650.00",
    "date": "2026-10-01",
    "description": "Rent",
    "category": "Housing",
    "is_fixed": "fixed",
}


class ExpenseFormTests(TestCase):
    def test_accepts_fixed_rent_as_exact_money(self):
        form = ExpenseForm(RENT)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], Decimal("650.00"))
        self.assertEqual(form.cleaned_data["date"], date(2026, 10, 1))
        self.assertEqual(form.cleaned_data["category"], "Housing")
        self.assertIs(form.cleaned_data["is_fixed"], True)

    def test_variable_choice_is_not_fixed(self):
        form = ExpenseForm({**RENT, "is_fixed": "variable"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIs(form.cleaned_data["is_fixed"], False)

    def test_missing_category_uses_story_message(self):
        form = ExpenseForm({**RENT, "category": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("Choose a category", form.errors["category"])

    def test_unknown_category_is_rejected(self):
        form = ExpenseForm({**RENT, "category": "Yachts"})

        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_requires_fixed_or_variable(self):
        form = ExpenseForm({**RENT, "is_fixed": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("is_fixed", form.errors)

    def test_rejects_zero_amount(self):
        form = ExpenseForm({**RENT, "amount": "0.00"})

        self.assertFalse(form.is_valid())
        self.assertIn("Amount must be greater than zero", form.errors["amount"])

    def test_accepts_smallest_amount(self):
        form = ExpenseForm({**RENT, "amount": "0.01"})

        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_amounts_that_are_not_exact_cents(self):
        # Fractions of a cent, more than 8 whole digits, and non-numbers.
        for amount in ["0.001", "12.345", "100000000.00", "abc", "NaN", "Infinity"]:
            with self.subTest(amount=amount):
                form = ExpenseForm({**RENT, "amount": amount})

                self.assertFalse(form.is_valid())
                self.assertIn("amount", form.errors)

    def test_requires_a_valid_date(self):
        for value in ["", "2026-13-01"]:
            with self.subTest(date=value):
                form = ExpenseForm({**RENT, "date": value})

                self.assertFalse(form.is_valid())
                self.assertIn("date", form.errors)

    def test_blank_or_whitespace_description_is_rejected(self):
        # Each displays as nothing: a zero-width space, joiner and byte-order mark,
        # a control character, and combining marks with no letter to attach to.
        # Also the blank Braille pattern and Hangul fillers, which are letters or
        # symbols in Unicode but draw as empty space.
        for value in [
            "", "   ", "​", " ‍﻿ ", "\x07", "́", "⃝",
            "⠀", "ㅤ", "ᅟᅠ", "ﾠ",
        ]:
            with self.subTest(description=value):
                form = ExpenseForm({**RENT, "description": value})

                self.assertFalse(form.is_valid())
                self.assertIn("Enter an expense description.", form.errors["description"])


class RecordExpenseViewTests(TestCase):
    def setUp(self):
        self.student = get_user_model().objects.create_user(username="student")
        self.client.force_login(self.student)

    def test_signed_in_student_can_open_expense_form(self):
        response = self.client.get(reverse("record_expense"))

        self.assertContains(response, '<select name="category"')
        self.assertContains(response, 'type="radio" name="is_fixed" value="fixed"')
        self.assertContains(response, 'type="radio" name="is_fixed" value="variable"')

    def test_anonymous_get_redirects_to_login(self):
        response = Client().get(reverse("record_expense"))

        self.assertRedirects(response, reverse("sign_in") + "?next=" + reverse("record_expense"))

    def test_negative_amount_shows_error_and_saves_nothing(self):
        response = self.client.post(reverse("record_expense"), {**RENT, "amount": "-5.00"})

        self.assertContains(response, "Amount must be greater than zero")
        self.assertFalse(Transaction.objects.filter(is_demo=False).exists())

    def test_tampered_type_value_is_rejected(self):
        response = self.client.post(reverse("record_expense"), {**RENT, "is_fixed": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("is_fixed", response.context["form"].errors)
        self.assertFalse(Transaction.objects.filter(is_demo=False).exists())

    def test_anonymous_post_redirects_without_saving(self):
        response = Client().post(reverse("record_expense"), RENT)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Transaction.objects.filter(description="Rent").exists())

    def test_post_without_csrf_token_is_rejected_without_saving(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.student)

        response = csrf_client.post(reverse("record_expense"), RENT)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Transaction.objects.filter(description="Rent").exists())

    def test_fixed_expense_is_saved_with_category(self):
        response = self.client.post(reverse("record_expense"), RENT, follow=True)

        expense = Transaction.objects.get(description="Rent", is_demo=False)
        self.assertEqual(expense.kind, Transaction.Kind.EXPENSE)
        self.assertEqual(expense.owner, self.student)
        self.assertEqual(expense.amount, Decimal("650.00"))
        self.assertEqual(expense.category, "Housing")
        self.assertTrue(expense.is_fixed)
        self.assertEqual(expense.signed_amount, Decimal("-650.00"))
        self.assertContains(response, "Expense saved.")

    def test_variable_expense_is_saved_as_not_fixed(self):
        self.client.post(
            reverse("record_expense"),
            {**RENT, "description": "Coffee", "category": "Food", "is_fixed": "variable"},
        )

        self.assertFalse(Transaction.objects.get(description="Coffee").is_fixed)

    def test_missing_category_shows_error_and_saves_nothing(self):
        response = self.client.post(
            reverse("record_expense"),
            {**RENT, "amount": "12.50", "category": ""},
        )

        self.assertContains(response, "Choose a category")
        self.assertFalse(Transaction.objects.filter(is_demo=False).exists())

    def test_invisible_only_description_shows_error_and_saves_nothing(self):
        for description in ["​", "⠀"]:
            with self.subTest(description=description):
                response = self.client.post(
                    reverse("record_expense"), {**RENT, "description": description}
                )

                self.assertContains(response, "Enter an expense description.")
                self.assertFalse(Transaction.objects.filter(is_demo=False).exists())

    def test_description_with_visible_text_keeps_its_characters(self):
        # Joiners and combining accents inside visible text are kept as typed.
        for description in ["Caf‍e", "Café"]:
            with self.subTest(description=description):
                self.client.post(reverse("record_expense"), {**RENT, "description": description})

                self.assertTrue(Transaction.objects.filter(description=description).exists())

    def test_html_and_sql_like_descriptions_are_stored_as_plain_text(self):
        description = "<script>alert(1)</script>'; DROP TABLE transactions_transaction; --"

        self.client.post(reverse("record_expense"), {**RENT, "description": description})
        response = self.client.post(
            reverse("record_expense"),
            {**RENT, "description": description, "category": ""},
        )

        self.assertEqual(Transaction.objects.get(is_demo=False).description, description)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_identical_expenses_are_both_saved(self):
        # Two coffees on the same day are two real expenses, so identical entries
        # are allowed. The redirect after saving stops a page refresh resubmitting.
        response = self.client.post(reverse("record_expense"), RENT)
        self.client.post(reverse("record_expense"), RENT)

        self.assertRedirects(response, reverse("record_expense"))
        self.assertEqual(Transaction.objects.filter(description="Rent").count(), 2)

    def test_post_cannot_override_kind_or_demo_flag(self):
        self.client.post(
            reverse("record_expense"),
            {**RENT, "kind": "income", "is_demo": "on"},
        )

        expense = Transaction.objects.get(description="Rent")
        self.assertEqual(expense.kind, Transaction.Kind.EXPENSE)
        self.assertFalse(expense.is_demo)
