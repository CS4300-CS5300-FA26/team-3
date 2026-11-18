"""Category comparison shared by the dashboard and the spending fallback page."""
from collections import defaultdict
from decimal import Decimal


def category_totals(entries):
    amounts = defaultdict(lambda: Decimal("0.00"))
    for entry in entries:
        if entry["kind"] == "expense":
            amounts[entry["category"]] += entry["amount"]
    totals = sorted(amounts.items(), key=lambda row: (-row[1], row[0]))
    largest = totals[0][1] if totals else None
    total_spent = sum(amounts.values())
    return [
        {"category": category, "total": amount, "width": f"{amount * 100 / largest:.2f}",
         "share": f"{amount * 100 / total_spent:.2f}"}
        for category, amount in totals
    ]
