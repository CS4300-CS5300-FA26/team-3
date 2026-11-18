from datetime import date
from decimal import Decimal
from unittest.mock import patch

from behave import given, then, when
from django.urls import reverse


@when('I select "Explain my spending" for October 2026')
def explain_october_spending(context):
    context.summary_service = patch(
        "accounts.views.generate_spending_summary",
        return_value=[
            "Housing totaled $200.00.",
            "Food totaled $120.00.",
            "Books totaled $60.00.",
            "Ignored fourth observation.",
        ],
    )
    context.generate_summary = context.summary_service.start()
    context.add_cleanup(context.summary_service.stop)
    context.response = context.client.post(
        reverse("explain_spending"),
        {
            "month": "2026-10",
            "period": "selected_month",
            "explain_spending": "Explain my spending",
        },
    )


@given("I have at least 10 transactions in October 2026")
def enough_october_activity(context):
    totals = [("Housing", "200.00", 4), ("Food", "120.00", 4), ("Books", "60.00", 2)]
    for category, amount, count in totals:
        for index in range(count):
            context.Transaction.objects.create(
                owner=context.student,
                kind=context.Transaction.Kind.EXPENSE,
                amount=Decimal(amount) / count,
                date=date(2026, 10, index + 1),
                description=f"{category} purchase {index}",
                category=category,
            )
    context.expected_summary_categories = {category for category, _, _ in totals}
    context.expected_summary_amounts = {Decimal(amount) for _, amount, _ in totals}


@given("I have fewer than 10 transactions in the selected period")
def insufficient_activity(context):
    for index in range(9):
        context.Transaction.objects.create(
            owner=context.student,
            kind=context.Transaction.Kind.EXPENSE,
            amount=Decimal("10.00"),
            date=date(2026, 10, index + 1),
            description=f"October purchase {index}",
            category="Food",
        )
    context.summary_service = patch("accounts.views.generate_spending_summary")
    context.generate_summary = context.summary_service.start()
    context.add_cleanup(context.summary_service.stop)


@then("I see at most 3 observations")
def at_most_three_observations(context):
    assert context.response.status_code == 200
    assert len(context.response.context["summary_observations"]) <= 3


@then("each observation names a category and a dollar amount from my own transactions")
def observations_are_grounded(context):
    observations = context.response.context["summary_observations"]
    for observation in observations:
        assert any(category in observation for category in context.expected_summary_categories)
        assert any(f"${amount:.2f}" in observation for amount in context.expected_summary_amounts)


@then("no request is sent to the AI service")
def ai_service_is_not_called(context):
    context.generate_summary.assert_not_called()
