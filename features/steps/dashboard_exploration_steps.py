"""#74 exploration through dashboard URLs and their rendered link targets."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from behave import given, when, then


def dashboard(context, params):
    with patch("accounts.views.timezone.localdate", return_value=date(2026, 11, 16)):
        context.response = context.client.get("/dashboard/", {"month": "2026-11", **params})


def follow(context, url):
    with patch("accounts.views.timezone.localdate", return_value=date(2026, 11, 16)):
        context.response = context.client.get(url)


@given("my exploration records span November and October")
def records(context):
    for day, kind, amount, category in [
        ("2026-11-01", "income", "100", ""),
        ("2026-11-03", "expense", "0.10", "Food"),
        ("2026-11-03", "expense", "0.20", "Food"),
        ("2026-11-03", "expense", "2.00", "Books"),
        ("2026-11-30", "expense", "5.00", "Food"),
        ("2026-10-03", "expense", "8.00", "Food"),
    ]:
        context.Transaction.objects.create(owner=context.student, date=day, kind=kind,
                                           amount=amount, category=category, description="Exploration")


@when("I open November exploration with All time history")
def all_time(context):
    dashboard(context, {"period": "all"})


@when("I follow the Food category bar")
def category_bar(context):
    row = next(row for row in context.response.context["categories"] if row["category"] == "Food")
    follow(context, row["url"])


@then("only my November Food expenses are listed")
def food_only(context):
    rows = list(context.response.context["transactions"])
    assert len(rows) == 3
    assert all(t.kind == "expense" and t.category == "Food" and t.date.month == 11 for t in rows)


@then("the monthly figures still include every November transaction")
def monthly_figures(context):
    assert context.response.context["monthly_income"] == Decimal("100")
    assert context.response.context["monthly_expenses"] == Decimal("7.30")


@when("I explore Food expenses on November 3")
def day_food(context):
    dashboard(context, {"kind": "expense", "category": "Food", "date": "2026-11-03"})


@when("I remove the category criterion")
def remove_category(context):
    criterion = next(f for f in context.response.context["drilldown_filters"] if f["key"] == "category")
    follow(context, criterion["url"])


@then("all my expenses on November 3 are listed")
def expenses_on_day(context):
    rows = list(context.response.context["transactions"])
    assert len(rows) == 3
    assert all(t.kind == "expense" and t.date == date(2026, 11, 3) for t in rows)


@when("I clear the exploration filters")
def clear(context):
    follow(context, context.response.context["clear_filters_url"])


@then("all my November transactions are listed")
def november(context):
    rows = list(context.response.context["transactions"])
    assert len(rows) == 5
    assert all(t.date.month == 11 for t in rows)


@when("I request All time with stale monthly criteria")
def stale(context):
    dashboard(context, {"period": "all", "kind": "expense", "category": "Food", "date": "2026-11-03"})


@then("all my personal exploration records are listed")
def all_records(context):
    assert len(context.response.context["transactions"]) == 6


@then("no exploration criteria remain")
def no_criteria(context):
    assert context.response.context["drilldown_filters"] == []


@when("I view November exploration on November 16")
def cutoff(context):
    dashboard(context, {})


@then("the chart includes flat zero-spend days through November 16")
def daily(context):
    days = context.response.context["spending_days"]
    assert len(days) == 16
    assert days[-1]["date"] == date(2026, 11, 16)
    assert days[2]["total"] == days[3]["total"] == Decimal("2.30")
    assert days[3]["amount"] == Decimal("0")


@then("future expenses remain in the monthly total while the chart labels its end date")
def future(context):
    assert context.response.context["monthly_expenses"] == Decimal("7.30")
    assert context.response.context["chart_total"] == Decimal("2.30")
    assert "through Nov 16" in context.response.content.decode()
    assert "future-dated expenses." not in context.response.content.decode()
