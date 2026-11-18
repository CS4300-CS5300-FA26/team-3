"""Monthly dashboard data and links. Money stays decimal; SVG coordinates are display only."""
from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_CEILING
from urllib.parse import urlencode

from django.urls import reverse

from transactions.spending import category_totals


def month_history_url(month, **criteria):
    return reverse("dashboard") + "?" + urlencode({
        "month": month.isoformat()[:7], "period": "selected_month", **criteria,
    }) + "#history"


def drilldown_context(params, month, period):
    # Preset selection deliberately retires all monthly drill-down criteria.
    criteria = {}
    if period == "selected_month":
        if params.get("kind") in ("income", "expense"):
            criteria["kind"] = params["kind"]
        category = params.get("category", "")
        if category and len(category) <= 50:
            criteria["category"] = category
        try:
            day = date.fromisoformat(params.get("date", ""))
            if day.isoformat() == params["date"] and day.replace(day=1) == month:
                criteria["date"] = day.isoformat()
        except ValueError:
            pass
    labels = {"kind": {"income": "Income", "expense": "Expenses"}.get(criteria.get("kind")),
              "category": criteria.get("category"), "date": criteria.get("date")}
    filters = [
        {"key": key, "label": labels[key],
         "url": month_history_url(month, **{k: v for k, v in criteria.items() if k != key})}
        for key in criteria
    ]
    return criteria, filters


def monthly_context(transactions, month, today):
    # Read stored Decimal amounts before adding: SQLite SUM uses floating point.
    entries = list(transactions.values("kind", "amount", "date", "category"))
    income = sum((row["amount"] for row in entries if row["kind"] == "income"), Decimal("0.00"))
    expenses = sum((row["amount"] for row in entries if row["kind"] == "expense"), Decimal("0.00"))
    categories = category_totals(entries)
    for row in categories:
        row["url"] = month_history_url(month, kind="expense", category=row["category"])

    month_end = date(month.year, month.month, monthrange(month.year, month.month)[1])
    cutoff = min(today, month_end)
    daily = defaultdict(lambda: Decimal("0.00"))
    for row in entries:
        if row["kind"] == "expense" and row["date"] <= cutoff:
            daily[row["date"]] += row["amount"]
    running = Decimal("0.00")
    days = []
    if cutoff >= month:
        for day in range(1, cutoff.day + 1):
            day_date = month.replace(day=day)
            amount = daily.get(day_date, Decimal("0.00"))
            running += amount
            days.append({"date": day_date, "amount": amount, "total": running,
                         "url": month_history_url(month, kind="expense", date=day_date.isoformat())})

    # Step segments keep zero-spend days flat; there is no invented smoothing.
    # The y axis always starts at zero, including an entirely empty month.
    step = Decimal(10) ** max(0, running.adjusted())
    scale = (running / step).to_integral_value(rounding=ROUND_CEILING) * step or Decimal("1.00")
    # Compact axis labels keep large totals readable on phones; exact amounts
    # remain in the chart heading, points and day selector.
    divisor, suffix = (Decimal("1000000"), "m") if scale >= 1000000 else (
        (Decimal("1000"), "k") if scale >= 1000 else (Decimal("1"), "")
    )
    axis_labels = [f"${value / divisor:.2f}".rstrip("0").rstrip(".") + suffix
                   for value in (scale, scale / 2)]
    path = ""
    for index, point in enumerate(days):
        point["x"] = f"{Decimal(76) + Decimal(404) * index / max(len(days) - 1, 1):.2f}"
        point["y"] = f"{Decimal(120) - Decimal(100) * point['total'] / scale:.2f}"
        path += (f"M {point['x']} {point['y']}" if index == 0
                 else f" H {point['x']} V {point['y']}")
    return {
        "monthly_income": income, "monthly_expenses": expenses,
        "remaining_budget": income - expenses, "budget_transaction_count": len(entries),
        "categories": categories, "spending_days": days, "chart_path": path,
        "chart_total": running, "chart_axis_max": axis_labels[0], "chart_axis_mid": axis_labels[1],
        "chart_cutoff": cutoff if days else None, "future_expenses": expenses - running,
        "income_url": month_history_url(month, kind="income"),
        "expense_url": month_history_url(month, kind="expense"),
        "clear_filters_url": month_history_url(month),
        "month_end": month_end,
    }
