import re


def generate_spending_summary(category_totals):
    """Return plain-language observations from already-aggregated spending data."""
    return [
        f"{row['category']} was your largest category at ${row['total']:.2f}."
        for row in category_totals[:3]
    ]


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