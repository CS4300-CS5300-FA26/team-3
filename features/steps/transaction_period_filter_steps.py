from datetime import date
from decimal import Decimal
from unittest.mock import patch

from behave import given, then, when
from django.urls import reverse


PERIOD_VALUES = {
    "Last 3 days": "last_3_days",
    "Last 7 days": "last_7_days",
    "Last 14 days": "last_14_days",
    "This month": "this_month",
    "This quarter": "this_quarter",
    "All time": "all",
}


def _create_transaction(context, kind, amount, transaction_date, description, owner=None):
    return context.Transaction.objects.create(
        kind=kind,
        amount=Decimal(amount),
        date=transaction_date,
        description=description,
        category="Food" if kind == context.Transaction.Kind.EXPENSE else "",
        owner=owner or context.student,
    )


def _get_dashboard(context, period):
    with patch("accounts.views.timezone.localdate", return_value=context.today):
        context.response = context.client.get(
            reverse("dashboard"), {"period": period}
        )
    return context.response


@given("I am signed in and today is {today}")
def today_with_boundary_transactions(context, today):
    context.today = date.fromisoformat(today)
    dates = [
        date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 31),
        date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 8),
        date(2026, 11, 9), date(2026, 11, 12), date(2026, 11, 13),
        date(2026, 11, 15), date(2026, 11, 16),
    ]
    for index, transaction_date in enumerate(dates):
        _create_transaction(
            context,
            context.Transaction.Kind.INCOME,
            "1.00",
            transaction_date,
            f"Boundary transaction {index}",
        )
    context.other_dates = set(dates)


@when('I select "{period}"')
def select_period(context, period):
    assert period in PERIOD_VALUES, f"Unknown period preset: {period}"
    _get_dashboard(context, PERIOD_VALUES[period])


@then("only my transactions dated from {start} through {end} inclusive are listed")
def listed_transactions_are_in_range(context, start, end):
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    transactions = list(context.response.context["transactions"])
    transaction_dates = {transaction.date for transaction in transactions}

    assert context.response.status_code == 200
    assert all(start_date <= transaction.date <= end_date for transaction in transactions)
    assert start_date in transaction_dates
    assert end_date in transaction_dates
    assert len(transactions) == sum(
        start_date <= transaction_date <= end_date
        for transaction_date in context.other_dates
    )


@given("I have income of ${income} and expenses of ${expenses} in the selected period")
def selected_period_totals(context, income, expenses):
    context.today = date(2026, 11, 15)
    _create_transaction(context, "income", income, date(2026, 11, 15), "Selected income")
    _create_transaction(context, "expense", expenses, date(2026, 11, 14), "Selected expense")
    context.baseline_income = Decimal(income)
    context.baseline_expense = Decimal(expenses)


@given("I have other transactions outside that period")
def outside_period_transactions(context):
    _create_transaction(
        context, "expense", "100.00", date(2026, 11, 1), "Outside period expense"
    )
    from accounts.models import LowBalanceThreshold

    LowBalanceThreshold.objects.create(owner=context.student, amount=Decimal("60.00"))
    baseline = _get_dashboard(context, "all")
    context.baseline_budget = baseline.context["remaining_budget"]
    context.baseline_warning = baseline.context["show_low_balance_warning"]


@when("I filter my transaction history")
def filter_history(context):
    _get_dashboard(context, "last_3_days")


@then("the income total is ${income} and the expense total is ${expenses}")
def selected_totals_are_displayed(context, income, expenses):
    assert context.response.context["income_total"] == Decimal(income)
    assert context.response.context["expense_total"] == Decimal(expenses)


@then("my remaining budget and low-balance warnings are unchanged")
def monthly_budget_is_unchanged(context):
    assert context.response.context["remaining_budget"] == context.baseline_budget
    assert context.response.context["show_low_balance_warning"] == context.baseline_warning


@given("I have no transactions in the selected period")
def no_transactions_in_selected_period(context):
    context.today = date(2026, 11, 15)
    _create_transaction(
        context, "income", "75.00", date(2026, 11, 1), "Outside selected period"
    )


@then("both income and expense totals are ${amount}")
def empty_totals_are_zero(context, amount):
    expected = Decimal(amount)
    assert context.response.context["income_total"] == expected
    assert context.response.context["expense_total"] == expected


@given("I have a time-period filter selected")
def have_time_filter_selected(context):
    context.today = date(2026, 11, 15)
    _create_transaction(context, "income", "25.00", context.today, "Recent income")
    _create_transaction(context, "expense", "8.00", date(2026, 10, 1), "Older expense")
    _get_dashboard(context, "last_3_days")


@then("all of my transactions are listed")
def all_personal_transactions_listed(context):
    listed = {item.description for item in context.response.context["transactions"]}
    assert listed == {"Recent income", "Older expense"}


@then("the income and expense totals reflect all of my transactions")
def all_time_totals(context):
    assert context.response.context["income_total"] == Decimal("25.00")
    assert context.response.context["expense_total"] == Decimal("8.00")
