"""Token redaction at the loggers that emit registration URLs."""
import logging
from urllib.parse import unquote
from types import SimpleNamespace

from django.core.servers.basehttp import WSGIRequestHandler

from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from accounts.verification import issue_verification_token


class VerificationLoggingTests(SimpleTestCase):
    def setUp(self):
        self.token = issue_verification_token("student@example.com")
        self.url = reverse("accounts:verify", args=[self.token])

    def test_csrf_rejection_redacts_token_before_view_runs(self):
        with self.assertLogs("django.security.csrf", level="WARNING") as logs:
            response = Client(enforce_csrf_checks=True).post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.token, str(logs.output))
        self.assertIn("Forbidden", str(logs.output))

    def test_emitters_redact_raw_fields_without_changing_live_request(self):
        request = RequestFactory().get(self.url, HTTP_REFERER="https://testserver" + self.url)
        request.resolver_match = resolve(self.url)
        for name in ["django.security.csrf", "django.request", "django.server", "mangum.http"]:
            with self.subTest(logger=name), self.assertLogs(name, level="WARNING") as logs:
                logging.getLogger(name).warning(
                    "GET %s status 400", self.url,
                    extra={"request": request, "kwargs": {"token": self.token}},
                )
            record = logs.records[0]
            diagnostic = str((record.msg, record.args, record.kwargs,
                              record.request.path, record.request.path_info,
                              record.request.META, record.request.resolver_match.kwargs))
            self.assertNotIn(self.token, diagnostic)
            self.assertIn("GET", record.getMessage())
            self.assertIn("400", record.getMessage())
        self.assertEqual(request.path, self.url)
        self.assertEqual(request.resolver_match.kwargs["token"], self.token)
        self.assertEqual(request.META["HTTP_REFERER"], "https://testserver" + self.url)

    def test_early_security_failures_redact_structured_request_and_traceback(self):
        with self.assertLogs("django.security.DisallowedHost", level="ERROR") as logs:
            self.assertEqual(self.client.get(self.url, HTTP_HOST="invalid.example").status_code, 400)
        record = logs.records[0]
        self.assertNotIn(self.token, record.request.path)
        self.assertNotIn(self.token, logging.Formatter().format(record))
        self.assertIn("DisallowedHost", record.exc_text)
        client = Client(enforce_csrf_checks=True)
        client.cookies["csrftoken"] = "a" * 32
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1):
            with self.assertLogs("django.security.RequestDataTooBig", level="ERROR") as logs:
                response = client.post(self.url, {"password": "oversize"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.token, logs.records[0].request.path)
        self.assertIn("RequestDataTooBig", logging.Formatter().format(logs.records[0]))

    def test_server_redacts_encoded_credentials_without_decoding_log_controls(self):
        encoded = "/%61ccounts/verify/" + self.token.replace(":", "%3A") + "/?next=%0Aforged%00%1B"
        server = SimpleNamespace(request=object(), log_date_time_string=lambda: "test-time")
        with self.assertLogs("django.server", level="INFO") as logs:
            WSGIRequestHandler.log_message(server, '"%s" %s %s',
                                          f"POST {encoded} HTTP/1.1", "403", "0")
        message = logs.records[0].getMessage()
        self.assertNotIn(self.token, unquote(message))
        self.assertIn("[redacted]", message)
        self.assertIn("%0Aforged%00%1B", message)
        self.assertNotIn("\n", message)
        with self.assertLogs("django.server", level="INFO") as logs:
            logging.getLogger("django.server").info("GET /search?q=hello%20world 200")
        self.assertEqual(logs.records[0].getMessage(), "GET /search?q=hello%20world 200")
