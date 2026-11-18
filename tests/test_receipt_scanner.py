import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from openai import APIConnectionError

from transactions.services.receipt_scanner import scan_receipt


class ReceiptScannerTests(SimpleTestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.image_path = Path(self.temp_dir.name) / "receipt.jpeg"
        self.image_path.write_bytes(b"fake receipt image")

        self.api_key_patch = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-api-key",
                "OPENAI_RECEIPT_MODEL": "gpt-4.1-mini",
            },
        )
        self.api_key_patch.start()
        self.addCleanup(self.api_key_patch.stop)

        self.client_patch = patch(
            "transactions.services.receipt_scanner.OpenAI"
        )
        self.mock_client_class = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

        self.mock_client = self.mock_client_class.return_value
        self.mock_create = self.mock_client.responses.create

    def set_response(self, amount):
        response = MagicMock()
        response.output_text = json.dumps({"amount": amount})
        self.mock_create.return_value = response

    def test_extracts_receipt_total(self):
        self.set_response("23.47")

        result = scan_receipt(self.image_path)

        self.assertEqual(result, Decimal("23.47"))

    def test_extracts_real_receipt_total(self):
        self.set_response("64.44")

        result = scan_receipt(self.image_path)

        self.assertEqual(result, Decimal("64.44"))

    def test_preserves_two_decimal_places(self):
        self.set_response("10.00")

        result = scan_receipt(self.image_path)

        self.assertEqual(result, Decimal("10.00"))
        self.assertEqual(str(result), "10.00")

    def test_returns_none_when_total_unreadable(self):
        self.set_response(None)

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_empty_response(self):
        response = MagicMock()
        response.output_text = ""
        self.mock_create.return_value = response

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_invalid_json(self):
        response = MagicMock()
        response.output_text = "not valid json"
        self.mock_create.return_value = response

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_invalid_amount(self):
        self.set_response("not a number")

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_negative_amount(self):
        self.set_response("-23.47")

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_missing_decimal_places(self):
        self.set_response("23.4")

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_numeric_amount(self):
        self.set_response(23.47)

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_missing_image(self):
        missing_path = Path(self.temp_dir.name) / "missing.jpeg"

        result = scan_receipt(missing_path)

        self.assertIsNone(result)

    def test_returns_none_for_empty_image(self):
        self.image_path.write_bytes(b"")

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_rejects_unsupported_file_type(self):
        text_file = Path(self.temp_dir.name) / "receipt.txt"
        text_file.write_text("TOTAL 23.47")

        with self.assertRaises(ValueError):
            scan_receipt(text_file)

        self.mock_create.assert_not_called()

    def test_missing_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(RuntimeError):
                scan_receipt(self.image_path)

        self.mock_create.assert_not_called()

    def test_handles_api_connection_error(self):
        self.mock_create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_sends_image_to_openai(self):
        self.set_response("23.47")

        scan_receipt(self.image_path)

        self.mock_create.assert_called_once()
        kwargs = self.mock_create.call_args.kwargs

        self.assertEqual(kwargs["model"], "gpt-4.1-mini")

        content = kwargs["input"][0]["content"]
        image = content[1]

        self.assertEqual(image["type"], "input_image")
        self.assertTrue(
            image["image_url"].startswith("data:image/jpeg;base64,")
        )

    def test_requests_structured_json(self):
        self.set_response("23.47")

        scan_receipt(self.image_path)

        kwargs = self.mock_create.call_args.kwargs
        output_format = kwargs["text"]["format"]

        self.assertEqual(output_format["type"], "json_schema")
        self.assertEqual(output_format["name"], "receipt_total")
        self.assertTrue(output_format["strict"])

    def test_uses_configured_model(self):
        self.set_response("23.47")

        with patch.dict(
            os.environ,
            {"OPENAI_RECEIPT_MODEL": "custom-vision-model"},
        ):
            scan_receipt(self.image_path)

        kwargs = self.mock_create.call_args.kwargs
        self.assertEqual(kwargs["model"], "custom-vision-model")

    def test_returns_none_for_json_array(self):
        response = MagicMock()
        response.output_text = '["23.47"]'
        self.mock_create.return_value = response

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)

    def test_returns_none_for_missing_amount_field(self):
        response = MagicMock()
        response.output_text = "{}"
        self.mock_create.return_value = response

        result = scan_receipt(self.image_path)

        self.assertIsNone(result)
