"""Bound receipt-provider work across users and application workers."""
from datetime import timedelta

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from transactions.models import ReceiptScanBudget


def claim_receipt_request(user_id):
    """Allow five scans per student and 100 overall per rolling hour.

    Failed provider calls consume admission too. Keep provider work outside the
    database lock, and keep the ledger independent of spending explanations.
    """
    source = salted_hmac("transactions.receipt", str(user_id), algorithm="sha256").hexdigest()
    with transaction.atomic():
        if connection.vendor == "sqlite":
            ReceiptScanBudget.objects.filter(pk=1).update(id=F("id"))
        budget, _ = ReceiptScanBudget.objects.select_for_update().get_or_create(pk=1)
        now = timezone.now()
        cutoff = (now - timedelta(hours=1)).timestamp()
        recent = [entry for entry in budget.admitted_at if entry[0] > cutoff]
        if len(recent) >= 100 or sum(entry[1] == source for entry in recent) >= 5:
            return False
        budget.admitted_at = [*recent, [now.timestamp(), source]]
        budget.save(update_fields=["admitted_at"])
    return True
