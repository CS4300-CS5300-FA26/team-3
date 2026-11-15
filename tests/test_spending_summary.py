import io
import json
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError

from accounts.spending_summary import (
    SpendingSummaryError,
    generate_spending_summary,
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
