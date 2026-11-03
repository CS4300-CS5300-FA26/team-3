"""Issue #20 category breakdown checks. Shared steps are in common_steps.py."""

from datetime import datetime
from decimal import Decimal
import re

from behave import given, register_type, then, when
import parse

from common_steps import money


@parse.with_pattern(r"[A-Z][a-z]+ \d{4}")
def month_name(text):
    return datetime.strptime(text, "%B %Y").date()


# A strict month type keeps this Given from also matching the
# "I have income of ... and expenses of ..." step in budget_steps.py.
register_type(MonthName=month_name)


def amounts_and_names(text):
    """Split "$650.00 Housing, $120.00 Food and $60.00 Books" or
    "Housing $650.00, Food $120.00 and Books $60.00" into its parts."""
    return [part.strip() for part in re.split(r",| and ", text)]


@given("I have {day:MonthName} expenses of {expenses}")
def monthly_expenses(context, day, expenses):
    for part in amounts_and_names(expenses):
        amount, category = part.split(" ", 1)
        context.Transaction.objects.create(
            owner=context.student,
            kind=context.Transaction.Kind.EXPENSE,
            amount=Decimal(money(amount.lstrip("$"))),
            date=day,
            description=f"{category} expense",
            category=category,
        )


@when("I view the category breakdown for {month}")
def view_breakdown(context, month):
    from django.urls import reverse

    period = datetime.strptime(month, "%B %Y").strftime("%Y-%m")
    context.response = context.client.get(reverse("spending_by_category"), {"month": period})


@then("I see a horizontal bar chart with one bar per category: {bars}")
def bar_chart(context, bars):
    assert context.response.status_code == 200
    expected = []
    for part in amounts_and_names(bars):
        category, amount = part.rsplit(" ", 1)
        expected.append((category, Decimal(money(amount.lstrip("$")))))

    rows = context.response.context["categories"]
    shown = [(row["category"], row["total"]) for row in rows]
    assert sorted(shown) == sorted(expected), f"Chart shows {shown}"

    html = context.response.content.decode()
    assert html.count('class="bar"') == len(expected), "Expected one bar per category"
    for category, amount in expected:
        assert f"{category}</span>" in html and f"${amount}" in html


@then("the categories are ordered from highest to lowest")
def ranked(context):
    totals = [row["total"] for row in context.response.context["categories"]]
    assert totals == sorted(totals, reverse=True), f"Totals are in order {totals}"

    # The page itself must list them in the same order.
    html = context.response.content.decode()
    positions = [html.index(f"{row['category']}</span>") for row in context.response.context["categories"]]
    assert positions == sorted(positions)
