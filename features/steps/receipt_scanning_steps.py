"""D10 receipt-scanning acceptance checks."""

from decimal import Decimal
from unittest.mock import patch
from io import BytesIO
from PIL import Image
from behave import then, when
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


def receipt_image():
    """Create a valid JPEG upload for acceptance tests."""
    buffer = BytesIO()

    Image.new("RGB", (10, 10), "white").save(
        buffer,
        format="JPEG",
    )

    return SimpleUploadedFile(
        "receipt.jpeg",
        buffer.getvalue(),
        content_type="image/jpeg",
    )


@when("I upload a receipt with a total of $64.44")
def upload_readable_receipt(context):
    with patch(
        "transactions.views.scan_receipt",
        return_value=Decimal("64.44"),
    ) as mock_scan:
        context.response = context.client.post(
            reverse("scan_receipt_upload"),
            {"receipt": receipt_image()},
        )
        assert mock_scan.call_count == 1


@when("I upload a receipt larger than 4 MiB")
def upload_receipt_over_transport_limit(context):
    image = receipt_image().read()
    image += b"x" * (4 * 1024 * 1024 + 1 - len(image))
    with patch("transactions.views.scan_receipt") as scanner:
        context.response = context.client.post(reverse("scan_receipt_upload"), {
            "receipt": SimpleUploadedFile("receipt.jpeg", image, content_type="image/jpeg"),
        })
        context.receipt_provider_calls = scanner.call_count


@when("I upload a multi-picture JPEG receipt")
def upload_multi_picture_receipt(context):
    buffer = BytesIO()
    Image.new("RGB", (10, 10), "white").save(
        buffer, format="MPO", save_all=True,
        append_images=[Image.new("RGB", (10, 10), "black")],
    )
    with patch("transactions.views.scan_receipt", return_value=Decimal("64.44")):
        context.response = context.client.post(reverse("scan_receipt_upload"), {
            "receipt": SimpleUploadedFile("receipt.jpeg", buffer.getvalue(), content_type="image/jpeg"),
        })


@then("the oversized receipt is rejected before scanning")
def oversized_receipt_rejected(context):
    assert context.response.status_code == 400
    assert "4 MB" in context.response.json()["error"]
    assert context.receipt_provider_calls == 0


@then("the scanner returns an amount of $64.44")
def check_scanned_total(context):
    assert context.response.status_code == 200
    assert context.response.json()["amount"] == "64.44"


@when("I upload a receipt with no readable total")
def upload_unreadable_receipt(context):
    with patch(
        "transactions.views.scan_receipt",
        return_value=None,
    ):
        context.response = context.client.post(
            reverse("scan_receipt_upload"),
            {"receipt": receipt_image()},
        )


@then("the scanner returns a manual-entry message")
def check_manual_entry_message(context):
    assert context.response.status_code == 200

    data = context.response.json()

    assert data["amount"] is None
    assert (
        data["message"]
        == "Could not read a total, please enter it manually"
    )


@then("I can manually save an expense of $25.00")
def save_manual_expense(context):
    response = context.client.post(
        reverse("record_expense"),
        {
            "amount": "25.00",
            "date": "2026-11-17",
            "description": "Manual receipt expense",
            "category": "Food",
            "is_fixed": "variable",
        },
    )

    assert response.status_code == 302

    expense = context.Transaction.objects.get(
        owner=context.student,
        description="Manual receipt expense",
        is_demo=False,
    )

    assert expense.amount == Decimal("25.00")
    assert expense.category == "Food"


@when("I upload an unsupported receipt file")
def upload_invalid_receipt(context):
    invalid_file = SimpleUploadedFile(
        "receipt.txt",
        b"not an image",
        content_type="text/plain",
    )

    context.response = context.client.post(
        reverse("scan_receipt_upload"),
        {"receipt": invalid_file},
    )


@then("the receipt upload is rejected")
def check_invalid_upload(context):
    assert context.response.status_code == 400
    assert (
        context.response.json()["error"]
        == "Unsupported receipt image format."
    )


@when("I sign out and attempt to scan a receipt")
def upload_while_signed_out(context):
    context.client.logout()

    context.response = context.client.post(
        reverse("scan_receipt_upload"),
        {"receipt": receipt_image()},
    )


@then("the receipt upload requires authentication")
def check_authentication(context):
    from django.conf import settings
    from django.shortcuts import resolve_url
    from urllib.parse import urlsplit

    assert context.response.status_code == 302

    redirect_path = urlsplit(context.response["Location"]).path
    expected_path = urlsplit(resolve_url(settings.LOGIN_URL)).path

    assert redirect_path == expected_path, (
        f"Expected redirect to {expected_path}, got {redirect_path}"
    )


@then("no expense is created by scanning")
def check_no_expense_created(context):
    assert (
        context.Transaction.objects.count()
        == context.transaction_count
    )


@when("I save the reviewed receipt as a monthly expense of $65.00")
def save_reviewed_receipt(context):
    context.response = context.client.post(reverse("record_expense"), {
        "amount": "65.00", "date": "2026-11-18", "description": "Reviewed receipt",
        "category": "Food", "is_fixed": "fixed", "recurrence": "monthly",
        "next_due_date": "2026-12-18", "reminder_days": "5",
    })


@then("the reviewed amount and monthly reminder settings are saved")
def reviewed_receipt_saved(context):
    assert context.response.status_code == 302
    expense = context.Transaction.objects.get(owner=context.student, description="Reviewed receipt")
    assert expense.amount == Decimal("65.00")
    assert expense.recurrence == "monthly"
    assert expense.reminder_days == 5


@when("the receipt provider is unavailable")
def provider_unavailable(context):
    with patch("transactions.views.scan_receipt", side_effect=RuntimeError("private provider details")):
        context.response = context.client.post(reverse("scan_receipt_upload"), {"receipt": receipt_image()})


@then("the receipt scan offers manual entry without provider details")
def safe_receipt_failure(context):
    assert context.response.status_code == 503
    assert "unavailable" in context.response.json()["error"]
    assert "private provider details" not in context.response.content.decode()


@when("I request six receipt scans within an hour")
def repeated_receipts(context):
    with patch("transactions.views.scan_receipt", return_value=Decimal("64.44")) as scanner:
        for _ in range(6):
            context.response = context.client.post(reverse("scan_receipt_upload"), {"receipt": receipt_image()})
        context.receipt_provider_calls = scanner.call_count


@then("only five scans reach the receipt provider")
def receipts_bounded(context):
    assert context.response.status_code == 429
    assert context.receipt_provider_calls == 5
