from decimal import Decimal
from unittest.mock import patch

from behave import given, when, then
from django.urls import reverse



@given("I am signed in for monthly spending details")
def details_user(context):
    context.execute_steps("Given an isolated personal dashboard")
    context.details_user = context.student


def incomes(context, count):
    from transactions.models import Transaction
    for _ in range(count):
        Transaction.objects.create(owner=context.details_user, kind="income", amount="1.00",
                                   date="2026-11-01", description="Private income")


@given("I have nine incomes and one expense in November")
def mixed_month(context):
    from transactions.models import Transaction
    incomes(context, 9)
    Transaction.objects.create(owner=context.details_user, kind="expense", amount="0.30",
                               date="2026-11-03", category="Food", description="Private expense")


@given("I have ten incomes and no expenses in November")
def income_month(context):
    incomes(context, 10)


def explain(context, observations):
    with patch("transactions.views.generate_spending_summary", return_value=observations) as provider:
        context.response = context.client.post(reverse("explain_spending") + "?month=2026-11&period=all&category=Missing",
                                               {"explain_spending": "1"})
        context.summary_calls = provider.call_args_list


@when("I explain November spending with an unrelated history filter")
def explain_month(context):
    explain(context, ["Food totaled $0.30."])


@then("the explanation receives only my November expense aggregates")
def aggregates(context):
    assert len(context.summary_calls) == 1
    assert context.summary_calls[0].args == ([{"category": "Food", "total": Decimal("0.30"), "count": 1}],)


@then("the details show the exact monthly total and category share")
def exact_details(context):
    assert context.response.context["total_spent"] == Decimal("0.30")
    assert context.response.context["categories"][0]["share"] == "100.00"


@then("the details explain that there are no expenses to summarize")
def no_expenses(context):
    assert not context.summary_calls
    assert "No expenses to summarize for this month." in context.response.content.decode()


@when("the November explanation provider returns no valid observations")
def invalid_summary(context):
    explain(context, ["Unknown totaled $999.00."])


@then("the details offer a safe failure and an explicit retry")
def failure_retry(context):
    html = context.response.content.decode()
    assert "Unable to generate spending summary right now." in html
    assert "Try again" in html


@when("I submit the dashboard Explain my spending action")
def dashboard_explain(context):
    import re
    from html import unescape

    page = context.client.get(reverse("dashboard"), {"month": "2026-11"})
    action = unescape(re.search(r'<form[^>]*data-spending-details[^>]*action="([^"]*)"',
                                page.content.decode()).group(1))
    with patch("transactions.views.generate_spending_summary", return_value=["Food totaled $0.30."]) as provider:
        context.response = context.client.post(action, {"explain_spending": "1"})
        context.summary_calls = provider.call_args_list


@then("the details show a generated summary without another generation button")
def already_explained(context):
    html = context.response.content.decode()
    assert "Generated summary" in html
    assert "Food totaled $0.30." in html
    assert 'class="explanation-form"' not in html


@when("the provider returns reasoning followed by a comma-punctuated summary")
def reasoning_summary(context):
    import io
    import json

    payload = {"output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "content": [{
            "type": "output_text",
            "text": '["Food, at $0.30, was your only spending category."]',
        }]},
    ]}
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
            patch("accounts.spending_summary.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())):
        context.response = context.client.post(reverse("explain_spending") + "?month=2026-11",
                                               {"explain_spending": "1"})


@then("the details show the comma-punctuated spending observation")
def comma_summary(context):
    assert context.response.status_code == 200
    assert "Food, at $0.30, was your only spending category." in context.response.content.decode()
