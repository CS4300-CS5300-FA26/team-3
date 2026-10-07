from datetime import date
from decimal import Decimal

from django.db import migrations


def seed_demo_transactions(apps, schema_editor):
    """Create synthetic transactions for the public demo page."""
    Transaction = apps.get_model("transactions", "Transaction")

    Transaction.objects.bulk_create(
        [
            Transaction(
                kind="income",
                amount=Decimal("1200.00"),
                date=date(2026, 10, 1),
                description="Part-time job",
                category="",
                is_demo=True,
            ),
            Transaction(
                kind="expense",
                amount=Decimal("45.75"),
                date=date(2026, 10, 3),
                description="Groceries",
                category="Food",
                is_demo=True,
            ),
            Transaction(
                kind="expense",
                amount=Decimal("28.50"),
                date=date(2026, 10, 5),
                description="Gas",
                category="Transportation",
                is_demo=True,
            ),
        ]
    )


def remove_demo_transactions(apps, schema_editor):
    """Remove transactions created specifically for the public demo."""
    Transaction = apps.get_model("transactions", "Transaction")
    Transaction.objects.filter(is_demo=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0004_transaction_is_demo"),
    ]

    operations = [
        migrations.RunPython(
            seed_demo_transactions,
            remove_demo_transactions,
        ),
    ]
