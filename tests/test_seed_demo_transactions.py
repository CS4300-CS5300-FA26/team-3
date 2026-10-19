from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from transactions.models import Transaction


class SeedDemoTransactionsTests(TestCase):
    def setUp(self):
        Transaction.objects.all().delete()

    def test_seeds_january_demo_budget(self):
        output = StringIO()
        call_command("seed_demo_transactions", stdout=output)

        rows = Transaction.objects.filter(is_demo=True, date__year=2027, date__month=1)
        self.assertEqual(rows.count(), 2)
        self.assertEqual(
            sum((row.signed_amount for row in rows), Decimal("0.00")),
            Decimal("625.00"),
        )
        for row in rows:
            row.full_clean()
        self.assertIn("Created 2 demo transactions", output.getvalue())

    def test_rerunning_does_not_duplicate_transactions(self):
        call_command("seed_demo_transactions", stdout=StringIO())
        original_ids = set(Transaction.objects.values_list("id", flat=True))
        output = StringIO()

        call_command("seed_demo_transactions", stdout=output)

        self.assertEqual(
            set(Transaction.objects.values_list("id", flat=True)), original_ids
        )
        self.assertIn("Created 0 demo transactions", output.getvalue())

    def test_preserves_existing_data_and_reuses_manual_example(self):
        manual = Transaction.objects.create(
            kind=Transaction.Kind.INCOME,
            amount=Decimal("900.00"),
            date=date(2027, 1, 5),
            description="January paycheck",
            is_demo=True,
        )
        private = Transaction.objects.create(
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("275.00"),
            date=date(2027, 1, 10),
            description="January groceries",
            category="Food",
        )
        unrelated = Transaction.objects.create(
            kind=Transaction.Kind.INCOME,
            amount=Decimal("75.00"),
            date=date(2026, 10, 1),
            description="Other demo income",
            is_demo=True,
        )
        before = list(Transaction.objects.order_by("id").values())
        output = StringIO()

        call_command("seed_demo_transactions", stdout=output)

        self.assertEqual(Transaction.objects.count(), 4)
        self.assertEqual(
            list(Transaction.objects.filter(
                pk__in=[manual.pk, private.pk, unrelated.pk]
            ).order_by("id").values()),
            before,
        )
        self.assertIn("Created 1 demo transactions", output.getvalue())
