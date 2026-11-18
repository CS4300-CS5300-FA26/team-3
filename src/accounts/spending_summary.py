import json
import os
import re
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from accounts.models import SpendingSummaryBudget


class SpendingSummaryError(RuntimeError):
    """Raised when the configured spending-summary provider cannot respond."""


def claim_summary_request(user_id):
    """Admit at most five requests per student and 100 overall per rolling hour.

    Like recovery admission, the database lock shares limits across workers.
    Failures consume admission too, and provider calls run outside the lock.
    """
    source = salted_hmac("accounts.summary", str(user_id), algorithm="sha256").hexdigest()
    with transaction.atomic():
        if connection.vendor == "sqlite":
            SpendingSummaryBudget.objects.filter(pk=1).update(id=F("id"))
        budget, _ = SpendingSummaryBudget.objects.select_for_update().get_or_create(pk=1)
        now = timezone.now()
        cutoff = (now - timedelta(hours=1)).timestamp()
        recent = [entry for entry in budget.admitted_at if entry[0] > cutoff]
        if len(recent) >= 100 or sum(entry[1] == source for entry in recent) >= 5:
            return False
        budget.admitted_at = [*recent, [now.timestamp(), source]]
        budget.save(update_fields=["admitted_at"])
    return True


def _summary_prompt(category_totals):
    totals = [
        {
            "category": row["category"],
            "total": f"{row['total']:.2f}",
            "count": row["count"],
        }
        for row in category_totals
    ]
    return (
        "Create at most 3 concise observations about this spending data. "
        "Mention only categories and dollar totals present in the data. "
        "Return a JSON array of strings and no other text.\n"
        f"Spending data: {json.dumps(totals)}"
    )


def _provider_text(response):
    if not isinstance(response, dict):
        raise SpendingSummaryError("Spending summary service returned invalid output.")

    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    text_parts = []
    output = response.get("output")
    if not isinstance(output, list):
        raise SpendingSummaryError("Spending summary service returned invalid output.")
    for item in output:
        if not isinstance(item, dict):
            raise SpendingSummaryError("Spending summary service returned invalid output.")
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise SpendingSummaryError("Spending summary service returned invalid output.")
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                text_parts.append(part["text"])

    if not text_parts:
        raise SpendingSummaryError("Spending summary service returned invalid output.")
    return "".join(text_parts)


def generate_spending_summary(category_totals):
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise SpendingSummaryError("Spending summary service is not configured.")

    payload = json.dumps({
        "model": os.environ.get("OPENAI_SPENDING_SUMMARY_MODEL", "gpt-6-luna"),
        "input": _summary_prompt(category_totals),
        "max_output_tokens": 240,
        "store": False,
    }).encode()
    request = Request(
        os.environ.get("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses"),
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            provider_response = json.loads(response.read().decode("utf-8"))
        observations = json.loads(_provider_text(provider_response))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError, TypeError):
        raise SpendingSummaryError("Spending summary service is unavailable.") from None
    if not isinstance(observations, list) or not all(
        isinstance(observation, str) for observation in observations
    ):
        raise SpendingSummaryError("Spending summary service returned invalid output.")
    return observations


def validate_spending_observations(observations, category_totals):
    known_totals = {
        row["category"]: f"${row['total']:.2f}" for row in category_totals
    }
    known_amounts = set(known_totals.values())
    valid_observations = []

    for observation in observations:
        if not isinstance(observation, str):
            continue

        monetary_tokens = set(re.findall(r"\$\d+(?:,\d{3})*(?:\.\d+)?", observation))
        if not monetary_tokens or not monetary_tokens.issubset(known_amounts):
            continue

        clauses = [
            clause.strip()
            for clause in re.split(r"(?:\band\b|;|[.!?](?:\s|$))", observation)
            if clause.strip()
        ]
        if not clauses:
            continue

        valid = True
        matched_category_count = 0
        for clause in clauses:
            category_matches = [
                category for category in known_totals
                if re.search(rf"\b{re.escape(category)}\b", clause, re.IGNORECASE)
            ]
            if not category_matches:
                if re.search(r"\$\d+(?:,\d{3})*(?:\.\d+)?", clause):
                    valid = False
                    break
                continue

            # Multiple pairs in one clause are ambiguous (amounts may be swapped).
            # Separate clauses such as "Food ... and Housing ..." remain supported.
            if len(category_matches) != 1:
                valid = False
                break
            matched_category_count += len(category_matches)
            clause_amounts = set(re.findall(r"\$\d+(?:,\d{3})*(?:\.\d+)?", clause))
            if clause_amounts != {known_totals[category_matches[0]]}:
                valid = False
                break

        if valid and matched_category_count:
            valid_observations.append(observation)
        if len(valid_observations) == 3:
            break
    return valid_observations
