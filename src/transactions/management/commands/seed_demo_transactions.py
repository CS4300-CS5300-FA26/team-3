from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from transactions.models import Transaction


class Command(BaseCommand):
    help = "Add January 2027 demo transactions, skipping matching existing records."

    @transaction.atomic
    def handle(self, *args, **options):
        examples = [
            {
                "kind": Transaction.Kind.INCOME,
                "amount": Decimal("900.00"),
                "date": date(2027, 1, 5),
                "description": "January paycheck",
                "category": "",
            },
            {
                "kind": Transaction.Kind.EXPENSE,
                "amount": Decimal("275.00"),
                "date": date(2027, 1, 10),
                "description": "January groceries",
                "category": "Food",
            },
        ]
        created_count = 0
        for fields in examples:
            fields.update(is_demo=True, is_fixed=False)
            # Also recognize examples previously entered through the Django shell.
            if not Transaction.objects.filter(**fields).exists():
                Transaction.objects.create(**fields)
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Created {created_count} demo transactions; "
            f"skipped {len(examples) - created_count} existing examples."
        ))
