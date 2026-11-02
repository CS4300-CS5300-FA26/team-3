from datetime import date
from decimal import Decimal

from behave import given, when, then


@given("I have an existing expense for transaction management")
def create_expense(context):
    context.transaction = context.Transaction.objects.create(
        owner=context.student,
        kind="expense",
        amount=Decimal("50.00"),
        date=date(2026, 10, 15),
        description="Groceries",
        category="Food",
        is_fixed=False,
    )


@when("I edit my expense amount to ${amount}")
def edit_expense(context, amount):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("edit_transaction", args=[context.transaction.pk]),
        {
            "amount": amount,
            "date": "2026-10-15",
            "description": "Groceries",
            "category": "Food",
            "is_fixed": "variable",
        },
    )


@then("my expense amount is updated to ${amount}")
def verify_edited_expense(context, amount):
    context.transaction.refresh_from_db()

    assert context.transaction.amount == Decimal(amount)


@then("my remaining budget reflects the edited expense")
def verify_edited_budget(context):
    from django.urls import reverse

    response = context.client.get(
        reverse("dashboard"),
        {"month": "2026-10"},
    )

    assert response.status_code == 200
    assert response.context["remaining_budget"] == Decimal("-75.00")


@when("I open the deletion confirmation page")
def open_delete_confirmation(context):
    from django.urls import reverse

    context.response = context.client.get(
        reverse("delete_transaction", args=[context.transaction.pk])
    )


@then("I see the deletion confirmation")
def verify_delete_confirmation(context):
    assert context.response.status_code == 200
    assert b"Confirm Delete" in context.response.content


@when("I confirm the transaction deletion")
def confirm_delete(context):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("delete_transaction", args=[context.transaction.pk])
    )


@then("the transaction no longer exists")
def verify_deleted(context):
    assert not context.Transaction.objects.filter(
        pk=context.transaction.pk
    ).exists()


@then("my remaining budget reflects the deleted expense")
def verify_deleted_budget(context):
    from django.urls import reverse

    response = context.client.get(
        reverse("dashboard"),
        {"month": "2026-10"},
    )

    assert response.status_code == 200
    assert response.context["remaining_budget"] == Decimal("0.00")


@when("I cancel transaction deletion")
def cancel_delete(context):
    from django.urls import reverse

    context.response = context.client.get(reverse("dashboard"))


@then("the transaction still exists")
def verify_transaction_exists(context):
    assert context.Transaction.objects.filter(
        pk=context.transaction.pk
    ).exists()


@given("the expense belongs to another user")
def change_transaction_owner(context):
    from django.contrib.auth import get_user_model

    other_user = get_user_model().objects.create_user(
        username="another-budget-student"
    )

    context.transaction.owner = other_user
    context.transaction.save()


@when("I attempt to edit the transaction")
def attempt_unauthorized_edit(context):
    from django.urls import reverse

    context.response = context.client.get(
        reverse("edit_transaction", args=[context.transaction.pk])
    )


@when("I attempt to delete the transaction")
def attempt_unauthorized_delete(context):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("delete_transaction", args=[context.transaction.pk])
    )


@then("the transaction request is rejected")
def verify_unauthorized_request(context):
    assert context.response.status_code == 404


@when("I view my transaction dashboard")
def view_dashboard(context):
    from django.urls import reverse

    context.response = context.client.get(
        reverse("dashboard"),
        {"month": "2026-10"},
    )


@then("I see Edit and Delete links for my transaction")
def verify_transaction_links(context):
    from django.urls import reverse

    assert context.response.status_code == 200

    edit_url = reverse(
        "edit_transaction",
        args=[context.transaction.pk],
    )

    delete_url = reverse(
        "delete_transaction",
        args=[context.transaction.pk],
    )

    content = context.response.content.decode()

    assert f'href="{edit_url}"' in content
    assert f'href="{delete_url}"' in content