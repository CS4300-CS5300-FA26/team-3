"""Receipt integration: validation, paid admission, and shared form boundaries."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from tests import test_receipt_upload


class ReceiptIntegrationTests(TestCase):
    setUp = test_receipt_upload.ReceiptUploadTests.setUp
    make_image = test_receipt_upload.ReceiptUploadTests.make_image

    @patch("transactions.views.scan_receipt", return_value=Decimal("64.44"))
    def test_paid_requests_are_bounded_per_student(self, scan):
        for _ in range(5):
            self.assertEqual(self.client.post(self.url, {"receipt": self.make_image()}).status_code, 200)
        response = self.client.post(self.url, {"receipt": self.make_image()})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(scan.call_count, 5)

    @patch("transactions.views.scan_receipt", return_value=Decimal("64.44"))
    @patch("transactions.views.MAX_RECEIPT_PIXELS", 50, create=True)
    def test_decoded_dimensions_are_bounded_before_scanning(self, scan):
        response = self.client.post(self.url, {"receipt": self.make_image()})
        self.assertEqual(response.status_code, 400)
        scan.assert_not_called()

    @patch("transactions.views.scan_receipt")
    def test_csrf_is_required_before_scanning(self, scan):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {"receipt": self.make_image()}).status_code, 403)
        scan.assert_not_called()

    def test_shared_receipt_controls_in_full_page_and_dialog(self):
        for headers in ({}, {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}):
            response = self.client.get(reverse("record_expense"), **headers)
            self.assertContains(response, "data-scan-receipt")
            self.assertContains(response, "data-cancel-scan")
            self.assertContains(response, "Recurrence schedule")

    @patch("transactions.views.scan_receipt", side_effect=RuntimeError("private provider error"))
    def test_provider_failures_consume_admission_and_keep_details_private(self, scan):
        for _ in range(5):
            response = self.client.post(self.url, {"receipt": self.make_image()})
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, "private provider error", status_code=503)
        self.assertEqual(self.client.post(self.url, {"receipt": self.make_image()}).status_code, 429)
        self.assertEqual(scan.call_count, 5)

    @patch("transactions.views.scan_receipt")
    def test_invalid_image_does_not_consume_admission(self, scan):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from transactions.models import ReceiptScanBudget
        response = self.client.post(self.url, {"receipt": SimpleUploadedFile("fake.jpg", b"fake", content_type="image/jpeg")})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReceiptScanBudget.objects.exists())
        scan.assert_not_called()

    @patch("transactions.views.scan_receipt", return_value=Decimal("64.44"))
    def test_supported_formats_decode_and_keep_amount_editable(self, scan):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from transactions.models import Transaction
        for image_format, mime in [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]:
            with self.subTest(image_format=image_format):
                stream = BytesIO()
                Image.new("RGB", (10, 10), "white").save(stream, format=image_format)
                upload = SimpleUploadedFile("receipt", stream.getvalue(), content_type=mime)
                response = self.client.post(self.url, {"receipt": upload})
                self.assertEqual(response.json(), {"amount": "64.44"})
        self.assertEqual(Transaction.objects.filter(owner=self.user).count(), 0)
        response = self.client.post(reverse("record_expense"), {
            "amount": "65.00", "date": "2026-11-18", "description": "Reviewed receipt",
            "category": "Food", "is_fixed": "fixed", "recurrence": "monthly",
            "next_due_date": "2026-12-18", "reminder_days": "5",
        })
        self.assertEqual(response.status_code, 302)
        saved = Transaction.objects.get(owner=self.user)
        self.assertEqual(saved.owner, self.user)
        self.assertEqual(saved.amount, Decimal("65.00"))
        self.assertEqual(saved.recurrence, "monthly")
        self.assertEqual(saved.reminder_days, 5)

    @patch("transactions.views.scan_receipt")
    def test_corrupt_decoded_image_and_decompression_bomb_are_safe(self, scan):
        from PIL import Image
        for failure in [OSError("corrupt"), Image.DecompressionBombError("too large")]:
            with self.subTest(failure=type(failure).__name__):
                with patch("transactions.views.Image.open", side_effect=failure):
                    response = self.client.post(self.url, {"receipt": self.make_image()})
                self.assertEqual(response.status_code, 400)
        scan.assert_not_called()

    def test_aggregate_budget_rolls_over_and_is_separate_from_summaries(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.models import SpendingSummaryBudget
        from transactions.models import ReceiptScanBudget
        from transactions.receipt_limits import claim_receipt_request
        now = timezone.now()
        with patch("transactions.receipt_limits.timezone.now", return_value=now):
            for user_id in range(20):
                for _ in range(5):
                    self.assertTrue(claim_receipt_request(user_id))
            self.assertFalse(claim_receipt_request(21))
        self.assertFalse(SpendingSummaryBudget.objects.exists())
        self.assertEqual(len(ReceiptScanBudget.objects.get().admitted_at), 100)
        with patch("transactions.receipt_limits.timezone.now", return_value=now + timedelta(hours=1)):
            self.assertTrue(claim_receipt_request(21))
        self.assertEqual(len(ReceiptScanBudget.objects.get().admitted_at), 1)


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL")
class ReceiptConcurrencyTests(TransactionTestCase):
    def test_concurrent_uploads_share_one_student_admission_limit(self):
        user = get_user_model().objects.create_user(username="concurrent-receipt")
        barrier = Barrier(8)

        def upload(_):
            close_old_connections()
            try:
                client = Client()
                client.force_login(user)
                barrier.wait(timeout=10)
                return client.post(reverse("scan_receipt_upload"), {
                    "receipt": test_receipt_upload.ReceiptUploadTests.make_image(self),
                }).status_code
            finally:
                close_old_connections()

        with patch("transactions.views.scan_receipt", return_value=Decimal("1.00")) as scan:
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(upload, range(8)))
        self.assertEqual(statuses.count(200), 5)
        self.assertEqual(statuses.count(429), 3)
        self.assertEqual(scan.call_count, 5)
