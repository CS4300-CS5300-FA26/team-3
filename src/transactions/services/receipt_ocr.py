import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache

MONEY_PATTERN = re.compile(r"\$?\s*(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}\b")



TOTAL_LABELS = (
    "grand total",
    "amount due",
    "balance due",
    "total",
)

EXCLUDED_LABELS = (
    "subtotal",
    "sub total",
    "total savings",
    "total discount",
    "total tax",
    "total number",
    "total items",
)


def extract_receipt_total(lines):
    """Return the most likely final receipt total, or None."""
    candidates = []

    for index, line in enumerate(lines):
        normalized = line.lower().strip()

        if any(label in normalized for label in EXCLUDED_LABELS):
            continue

        if not any(label in normalized for label in TOTAL_LABELS):
            continue

        matches = MONEY_PATTERN.findall(normalized)

        if not matches and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            matches = MONEY_PATTERN.findall(next_line)

        if not matches:
            continue

        try:
            amount = Decimal(
                matches[-1].replace("$", "").replace(",", "").strip()
            )
        except InvalidOperation:
            continue

        if amount > 0:
            candidates.append(amount)

    return candidates[-1] if candidates else None



@lru_cache(maxsize=1)
def get_ocr_engine():
    """Initialize and reuse the RapidOCR engine."""
    from rapidocr import RapidOCR

    return RapidOCR()


def scan_receipt(image_path):
    """Extract a receipt total, returning None if OCR cannot read it."""
    try:
        engine = get_ocr_engine()
        result = engine(image_path)
    except (OSError, ValueError) as exc:
        # Log expected image-loading and processing failures.
        import logging

        logging.getLogger(__name__).warning(
            "Receipt OCR failed: %s", exc
        )
        return None

    if result is None or not result.txts:
        return None

    return extract_receipt_total(result.txts)
