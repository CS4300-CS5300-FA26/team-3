from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse


class ReceiptUploadTests(TestCase):
    def setUp(self):
        self.url = reverse("scan_receipt_upload")
        self.user = get_user_model().objects.create_user(
            username="receipt_test_user",
            password="test-password-123",
        )
        self.client.force_login(self.user)

    def make_image(self, content_type="image/jpeg", size=None):
        """Generate a genuine JPEG image for upload tests."""
        buffer = BytesIO()

        image = Image.new("RGB", (10, 10), color="white")
        image.save(buffer, format="JPEG")

        image_bytes = buffer.getvalue()

        if size is not None and size > len(image_bytes):
            image_bytes += b"x" * (size - len(image_bytes))

        return SimpleUploadedFile(
            "receipt.jpg",
            image_bytes,
            content_type=content_type,
        )

    @patch("transactions.views.scan_receipt")
    def test_successful_receipt_scan(self, mock_scan):
        mock_scan.return_value = Decimal("64.44")

        response = self.client.post(
            self.url,
            {"receipt": self.make_image()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"amount": "64.44"},
        )
        mock_scan.assert_called_once()

    @patch("transactions.views.scan_receipt")
    def test_unreadable_receipt(self, mock_scan):
        mock_scan.return_value = None

        response = self.client.post(
            self.url,
            {"receipt": self.make_image()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["amount"])
        self.assertIn("message", response.json())
        mock_scan.assert_called_once()

    def test_missing_receipt(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_unsupported_file_type(self):
        receipt = SimpleUploadedFile(
            "receipt.txt",
            b"not an image",
            content_type="text/plain",
        )

        response = self.client.post(
            self.url,
            {"receipt": receipt},
        )

        self.assertEqual(response.status_code, 400)

    def test_oversized_receipt(self):
        receipt = self.make_image(
            size=5 * 1024 * 1024 + 1,
        )

        response = self.client.post(
            self.url,
            {"receipt": receipt},
        )

        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_login_required(self):
        self.client.logout()

        response = self.client.post(
            self.url,
            {"receipt": self.make_image()},
        )

        self.assertEqual(response.status_code, 302)

    @patch("transactions.views.scan_receipt")
    def test_missing_api_configuration(self, mock_scan):
        mock_scan.side_effect = RuntimeError(
            "OPENAI_API_KEY is not configured"
        )

        response = self.client.post(
            self.url,
            {"receipt": self.make_image()},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())
        mock_scan.assert_called_once()

    @patch("transactions.views.scan_receipt")
    def test_scan_does_not_create_transaction(self, mock_scan):
        from transactions.models import Transaction

        mock_scan.return_value = Decimal("23.47")

        before = Transaction.objects.count()

        response = self.client.post(
            self.url,
            {"receipt": self.make_image()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), before)

    @patch("transactions.views.scan_receipt")
    def test_rejects_fake_jpeg(self, mock_scan):
        """Reject non-image bytes even with an allowed MIME type."""
        fake_image = SimpleUploadedFile(
            "fake.jpeg",
            b"This is not actually an image.",
            content_type="image/jpeg",
        )

        response = self.client.post(
            self.url,
            {"receipt": fake_image},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Invalid or corrupted receipt image.",
        )
        mock_scan.assert_not_called()

    @patch("transactions.views.scan_receipt")
    def test_rejects_mismatched_image_format(self, mock_scan):
        """Reject a valid PNG falsely declared as a JPEG."""
        buffer = BytesIO()
        Image.new("RGB", (10, 10), "white").save(
            buffer,
            format="PNG",
        )

        receipt = SimpleUploadedFile(
            "fake.jpg",
            buffer.getvalue(),
            content_type="image/jpeg",
        )

        response = self.client.post(
            self.url,
            {"receipt": receipt},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Unsupported receipt image format.",
        )
        mock_scan.assert_not_called()
