import io
import json
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError

from accounts.spending_summary import (
    SpendingSummaryError,
    generate_spending_summary,
    validate_spending_observations,
)


class SpendingSummaryServiceTests(TestCase):
    totals = [
        {"category": "Housing", "total": Decimal("200.00"), "count": 4},
        {"category": "Food", "total": Decimal("120.00"), "count": 6},
    ]

    def response(self, observations):
        return io.BytesIO(json.dumps({"output_text": json.dumps(observations)}).encode())

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_SPENDING_SUMMARY_MODEL": "test-model"})
    @patch("accounts.spending_summary.urlopen")
    def test_sends_aggregated_totals_and_parses_observations(self, urlopen):
        urlopen.return_value = self.response(["Housing was $200.00."])

        result = generate_spending_summary(self.totals)

        self.assertEqual(result, ["Housing was $200.00."])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-model")
        self.assertFalse(payload["store"])
        self.assertIn('"category": "Housing"', payload["input"])
        self.assertIn('"total": "200.00"', payload["input"])
        self.assertNotIn("description", payload["input"])
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True)
    @patch("accounts.spending_summary.urlopen")
    def test_defaults_to_gpt_6_luna(self, urlopen):
        urlopen.return_value = self.response(["Housing was $200.00."])

        generate_spending_summary(self.totals)

        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["model"], "gpt-6-luna")

    @patch.dict("os.environ", {}, clear=True)
    @patch("accounts.spending_summary.urlopen")
    def test_missing_api_key_does_not_send_request(self, urlopen):
        with self.assertRaisesRegex(SpendingSummaryError, "not configured"):
            generate_spending_summary(self.totals)
        urlopen.assert_not_called()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("accounts.spending_summary.urlopen", side_effect=URLError("private details"))
    def test_network_failure_is_sanitized(self, urlopen):
        with self.assertRaisesRegex(SpendingSummaryError, "unavailable") as error:
            generate_spending_summary(self.totals)
        self.assertNotIn("private details", str(error.exception))
        urlopen.assert_called_once()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("accounts.spending_summary.urlopen")
    def test_invalid_provider_output_is_rejected(self, urlopen):
        urlopen.return_value = self.response({"not": "a list"})

        with self.assertRaisesRegex(SpendingSummaryError, "invalid"):
            generate_spending_summary(self.totals)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("accounts.spending_summary.urlopen")
    def test_provider_response_must_be_an_object(self, urlopen):
        urlopen.return_value = io.BytesIO(b"[]")

        with self.assertRaisesRegex(SpendingSummaryError, "invalid"):
            generate_spending_summary(self.totals)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("accounts.spending_summary.urlopen")
    def test_reasoning_items_before_text_output_are_skipped(self, urlopen):
        urlopen.return_value = io.BytesIO(json.dumps({
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [
                    {"type": "output_text", "text": '["Housing was $200.00."]'}
                ]},
            ]
        }).encode())

        self.assertEqual(
            generate_spending_summary(self.totals),
            ["Housing was $200.00."],
        )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("accounts.spending_summary.urlopen")
    def test_invalid_utf8_provider_response_is_rejected(self, urlopen):
        urlopen.return_value = io.BytesIO(b"\xff")

        with self.assertRaisesRegex(SpendingSummaryError, "unavailable"):
            generate_spending_summary(self.totals)


class SpendingObservationValidationTests(TestCase):
    totals = [
        {"category": "Housing", "total": Decimal("200.00")},
        {"category": "Food", "total": Decimal("20.00")},
    ]

    def test_every_category_and_amount_pair_must_match(self):
        observations = [
            "Housing totaled $200.00 and Food totaled $20.00.",
            "Housing totaled $200.00 and Food totaled $120.00.",
            "Housing totaled $200.00 and Travel totaled $20.00.",
        ]

        self.assertEqual(
            validate_spending_observations(observations, self.totals),
            ["Housing totaled $200.00 and Food totaled $20.00."],
        )

    def test_comma_punctuated_category_and_amount_pair_is_valid(self):
        observation = "Housing, at $200.00, was your largest category."

        self.assertEqual(
            validate_spending_observations([observation], self.totals),
            [observation],
        )

    def test_rejects_comma_separated_swapped_amounts_and_partial_money_tokens(self):
        self.assertEqual(validate_spending_observations([
            "Housing was $20.00, Food was $200.00.",
            "Food totaled $20.001.",
        ], self.totals), [])
