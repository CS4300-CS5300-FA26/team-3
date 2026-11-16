from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace
from transactions.services.receipt_ocr import extract_receipt_total


def test_extract_receipt_total():
    lines = [
        "Subtotal $21.50",
        "Tax $1.97",
        "TOTAL $23.47",
        "Cash $25.00",
        "Change $1.53",
    ]

    assert extract_receipt_total(lines) == Decimal("23.47")


def test_unreadable_receipt():
    lines = ["Thank you for shopping", "Have a nice day"]

    assert extract_receipt_total(lines) is None


def test_amount_due():
    lines = [
        "Subtotal $18.00",
        "Tax $1.50",
        "Amount Due $19.50",
    ]

    assert extract_receipt_total(lines) == Decimal("19.50")


def test_total_with_thousands_separator():
    lines = ["GRAND TOTAL $1,234.56"]

    assert extract_receipt_total(lines) == Decimal("1234.56")



def test_subtotal_is_not_final_total():
    lines = [
        "Subtotal $21.50",
        "Tax $1.97",
    ]

    assert extract_receipt_total(lines) is None


def test_total_savings_is_not_final_total():
    lines = [
        "Total Savings $5.00",
        "Amount Due $23.47",
    ]

    assert extract_receipt_total(lines) == Decimal("23.47")


def test_receipt_with_only_total_savings():
    lines = [
        "Total Savings $5.00",
        "Thank you for shopping",
    ]

    assert extract_receipt_total(lines) is None




@patch("transactions.services.receipt_ocr.get_ocr_engine")
def test_scan_receipt_success(mock_get_engine):
    mock_engine = mock_get_engine.return_value
    mock_engine.return_value = SimpleNamespace(
        txts=["Subtotal $21.50", "TOTAL $23.47"]
    )

    from transactions.services.receipt_ocr import scan_receipt

    assert scan_receipt("receipt.jpg") == Decimal("23.47")
    mock_engine.assert_called_once_with("receipt.jpg")


@patch("transactions.services.receipt_ocr.get_ocr_engine")
def test_scan_receipt_unreadable(mock_get_engine):
    mock_engine = mock_get_engine.return_value
    mock_engine.return_value = SimpleNamespace(
        txts=["Thank you for shopping"]
    )

    from transactions.services.receipt_ocr import scan_receipt

    assert scan_receipt("unreadable.jpg") is None


@patch("transactions.services.receipt_ocr.get_ocr_engine")
def test_scan_receipt_image_error(mock_get_engine):
    mock_get_engine.return_value.side_effect = OSError(
        "Cannot read image"
    )

    from transactions.services.receipt_ocr import scan_receipt

    assert scan_receipt("invalid.jpg") is None




def test_costco_receipt_split_total():
    lines = [
        "SUBTOTAL",
        "64.44",
        "TAX",
        "0.00",
        "TOTAL",
        "64.44",
        "CHIP Read",
        "APPROVED - Purchase",
        "AMOUNT:$64.44",
        "Costco Visa",
        "64.44",
        "CHANGE",
        "0.00",
    ]

    assert extract_receipt_total(lines) == Decimal("64.44")



def test_total_items_is_not_expense_total():
    lines = [
        "TOTAL NUMBER OF ITEMS SOLD",
        "6.00",
    ]

    assert extract_receipt_total(lines) is None


def test_amount_due_preferred_over_subtotal():
    lines = [
        "SUBTOTAL",
        "21.50",
        "TAX",
        "1.97",
        "AMOUNT DUE",
        "23.47",
    ]

    assert extract_receipt_total(lines) == Decimal("23.47")


def test_total_not_overridden_by_later_unrelated_total():
    lines = [
        "TOTAL",
        "64.44",
        "TOTAL NUMBER OF ITEMS SOLD",
        "6.00",
    ]

    assert extract_receipt_total(lines) == Decimal("64.44")
