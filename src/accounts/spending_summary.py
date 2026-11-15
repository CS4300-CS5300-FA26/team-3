import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SpendingSummaryError(RuntimeError):
    """Raised when the configured spending-summary provider cannot respond."""


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
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    text_parts = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                text_parts.append(content["text"])
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
            provider_response = json.loads(response.read().decode())
        observations = json.loads(_provider_text(provider_response))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, TypeError):
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
    valid_observations = []
    for observation in observations:
        if not isinstance(observation, str):
            continue
        if any(
            re.search(rf"\b{re.escape(category)}\b", observation)
            and amount in observation
            for category, amount in known_totals.items()
        ):
            valid_observations.append(observation)
        if len(valid_observations) == 3:
            break
    return valid_observations