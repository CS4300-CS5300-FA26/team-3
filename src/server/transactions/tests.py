from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Transaction


def make_transaction(**overrides):
    """Build an unsaved, valid expense; tests override the field under test."""
    fields = {
        "kind": Transaction.Kind.EXPENSE,
        "amount": Decimal("12.50"),
        "date": date(2026, 10, 6),
        "description": "Coffee",
        "category": "Food",
    }
    fields.update(overrides)
    return Transaction(**fields)


class TransactionAmountTests(TestCase):
    def test_zero_amount_is_rejected(self):
        transaction = make_transaction(amount=Decimal("0.00"))
        with self.assertRaises(ValidationError) as raised:
            transaction.full_clean()
        self.assertIn("amount", raised.exception.message_dict)

    def test_negative_amount_is_rejected(self):
        transaction = make_transaction(amount=Decimal("-5.00"))
        with self.assertRaises(ValidationError) as raised:
            transaction.full_clean()
        self.assertIn("amount", raised.exception.message_dict)

    def test_smallest_positive_amount_is_accepted(self):
        make_transaction(amount=Decimal("0.01")).full_clean()


class TransactionCategoryTests(TestCase):
    def test_expense_without_category_is_rejected(self):
        transaction = make_transaction(category="")
        with self.assertRaises(ValidationError) as raised:
            transaction.full_clean()
        self.assertEqual(raised.exception.message_dict["category"], ["Choose a category."])

    def test_expense_with_whitespace_only_category_is_rejected(self):
        transaction = make_transaction(category="   ")
        with self.assertRaises(ValidationError) as raised:
            transaction.full_clean()
        self.assertEqual(raised.exception.message_dict["category"], ["Choose a category."])

    def test_income_without_category_is_allowed(self):
        make_transaction(
            kind=Transaction.Kind.INCOME,
            amount=Decimal("1200.00"),
            description="Part-time job",
            category="",
        ).full_clean()


class TransactionDatabaseConstraintTests(TestCase):
    """Saving without calling full_clean() must still be refused by the database."""

    def assert_save_is_refused(self, **overrides):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_transaction(**overrides).save()
        self.assertEqual(Transaction.objects.count(), 0)

    def test_save_refuses_zero_amount(self):
        self.assert_save_is_refused(amount=Decimal("0.00"))

    def test_save_refuses_negative_amount(self):
        self.assert_save_is_refused(amount=Decimal("-5.00"))

    def test_save_refuses_expense_without_category(self):
        self.assert_save_is_refused(category="")

    def test_save_refuses_expense_with_whitespace_only_category(self):
        self.assert_save_is_refused(category="   ")

    def test_save_keeps_category_with_surrounding_spaces(self):
        make_transaction(category=" Food ").save()
        self.assertEqual(Transaction.objects.get().category, " Food ")

    def test_save_refuses_unknown_kind(self):
        self.assert_save_is_refused(kind="refund")

    def test_create_refuses_invalid_rows(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.create(
                kind=Transaction.Kind.EXPENSE,
                amount=Decimal("0.00"),
                date=date(2026, 10, 6),
                description="Coffee",
                category="",
            )
        self.assertEqual(Transaction.objects.count(), 0)

    def test_save_allows_uncategorized_income(self):
        make_transaction(
            kind=Transaction.Kind.INCOME,
            amount=Decimal("1200.00"),
            description="Part-time job",
            category="",
        ).save()
        self.assertEqual(Transaction.objects.count(), 1)


class TransactionSignedAmountTests(TestCase):
    def test_income_adds_to_the_budget(self):
        transaction = make_transaction(kind=Transaction.Kind.INCOME, amount=Decimal("1200.00"))
        self.assertEqual(transaction.signed_amount, Decimal("1200.00"))

    def test_expense_subtracts_from_the_budget(self):
        transaction = make_transaction(amount=Decimal("650.00"))
        self.assertEqual(transaction.signed_amount, Decimal("-650.00"))

    def test_saved_transactions_sum_to_remaining_budget(self):
        rows = [
            (Transaction.Kind.INCOME, "1200.00", "Part-time job", ""),
            (Transaction.Kind.EXPENSE, "650.00", "Rent", "Housing"),
            (Transaction.Kind.EXPENSE, "120.00", "Groceries", "Food"),
            (Transaction.Kind.EXPENSE, "60.00", "Textbook", "Books"),
        ]
        for kind, amount, description, category in rows:
            Transaction.objects.create(
                kind=kind,
                amount=Decimal(amount),
                date=date(2026, 10, 5),
                description=description,
                category=category,
            )

        remaining = sum(t.signed_amount for t in Transaction.objects.all())

        self.assertEqual(remaining, Decimal("370.00"))
