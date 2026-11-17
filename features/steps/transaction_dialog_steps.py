"""Exercise the same canonical transaction routes used by the dialog client."""
from behave import given, when, then


DIALOG = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@when("I submit an expense dialog with an invalid amount")
def invalid_expense_dialog(context):
    context.dialog_data = {"amount": "0", "date": "2026-11-16", "description": "Dialog lunch",
                          "category": "Food", "is_fixed": "variable"}
    context.response = context.client.post("/expense/", context.dialog_data, **DIALOG)


@then("the dialog keeps my description and shows its validation error")
def kept_dialog(context):
    assert context.response.status_code == 422
    html = context.response.content.decode()
    assert 'value="Dialog lunch"' in html
    assert "Amount must be greater than zero" in html


@when("I correct the dialog amount and save")
def correct_dialog(context):
    context.dialog_data["amount"] = "12.34"
    context.response = context.client.post("/expense/", context.dialog_data, **DIALOG)


@then("the expense is saved for my account without a redirect")
def saved_dialog(context):
    from decimal import Decimal

    assert context.response.status_code == 200
    assert context.response.json() == {"message": "Expense saved."}
    entry = context.Transaction.objects.get(owner=context.student, description="Dialog lunch")
    assert entry.amount == Decimal("12.34")


@given("I have a transaction to manage from the dashboard")
def managed_entry(context):
    context.entry = context.Transaction.objects.create(
        owner=context.student, kind="income", amount="30", date="2026-11-16", description="Work",
    )


@when("I change its description through the dialog")
def change_dialog(context):
    from django.urls import reverse

    context.response = context.client.post(reverse("edit_transaction", args=[context.entry.pk]), {
        "amount": "30", "date": "2026-11-16", "description": "More work",
    }, **DIALOG)


@then("the saved transaction has the new description")
def changed_dialog(context):
    assert context.response.status_code == 200
    assert context.response.json() == {"message": "Transaction updated."}
    context.entry.refresh_from_db()
    assert context.entry.description == "More work"


@when("I confirm deletion through the existing delete route")
def delete_dialog(context):
    from django.urls import reverse

    context.response = context.client.post(reverse("delete_transaction", args=[context.entry.pk]), **DIALOG)


@then("the transaction is deleted and confirmed without a redirect")
def deleted_dialog(context):
    assert context.response.status_code == 200
    assert context.response.json() == {"message": "Transaction deleted."}
    assert not context.Transaction.objects.filter(pk=context.entry.pk).exists()
