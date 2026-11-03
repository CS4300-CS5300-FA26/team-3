"""Issue #23: public recovery routes, tokens, and bounded admission."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from smtplib import SMTPException
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.identity import create_verified_user
from accounts.models import FailedSignIn, LoginAttempt, PasswordResetRateLimit
from transactions.models import Transaction


OLD_PASSWORD = "A-tide-of-bright-copper-42!"
NEW_PASSWORD = "Another-wave-of-silver-73!"
CONFIRMATION = "If an account matches, password reset instructions will be sent."
EXPIRED = "This link has expired. Request a new one."
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


@override_settings(MAILERS=MAILERS, SIGNUP_BASE_URL="http://testserver")
class PasswordResetViewTests(TestCase):
    def setUp(self):
        self.user = create_verified_user("student@uccs.edu", OLD_PASSWORD)
        self.request_url = reverse("accounts:forgot_password")

    def link(self, user=None, token=None):
        user = user or self.user
        return reverse("accounts:reset_password", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": token or default_token_generator.make_token(user),
        })

    def test_signin_link_and_uniform_confirmation_for_all_expected_outcomes(self):
        self.assertContains(self.client.get(reverse("sign_in")), f'href="{self.request_url}"')
        self.assertContains(self.client.get(self.request_url), "Email")
        for email in [" Student@UCCS.EDU. ", "nobody@uccs.edu", "bad", "<script>alert(1)</script>",
                      "student@uccs.edu\n", "a" * 151 + "@uccs.edu", ""]:
            response = self.client.post(self.request_url, {"email": email}, follow=True)
            self.assertContains(response, CONFIRMATION)
            if email:
                self.assertNotContains(response, email)
            self.assertEqual(response.redirect_chain, [(reverse("accounts:reset_sent"), 302)])
        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(mail.outbox[0].to, [self.user.email])
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("http://"))
        self.assertContains(self.client.get(link, follow=True), "New password")

    def test_ineligible_accounts_and_delivery_failure_keep_confirmation(self):
        self.user.is_active = False
        self.user.save()
        self.assertContains(self.client.post(self.request_url, {"email": self.user.email}, follow=True), CONFIRMATION)
        self.user.is_active = True
        self.user.set_unusable_password()
        self.user.save()
        self.assertContains(self.client.post(self.request_url, {"email": self.user.email}, follow=True), CONFIRMATION)
        self.user.set_password(OLD_PASSWORD)
        self.user.save()
        with patch("accounts.mail.send_mail", side_effect=SMTPException("private transport detail")):
            response = self.client.post(self.request_url, {"email": self.user.email}, follow=True)
        self.assertContains(response, CONFIRMATION)
        self.assertNotContains(response, "private transport detail")
        self.assertEqual(len(mail.outbox), 0)

    def test_sixth_email_request_is_throttled(self):
        for _ in range(6):
            self.assertContains(self.client.post(self.request_url, {"email": self.user.email}, follow=True), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 5)

    def test_completion_clears_lockout_preserves_budget_and_invalidates_sessions(self):
        sessions = [Client(), Client()]
        for client in sessions:
            client.force_login(self.user)
        self.user.refresh_from_db()
        now = timezone.now()
        LoginAttempt.objects.create(email=self.user.email, failed_count=5, blocked_until=now + timedelta(minutes=15))
        FailedSignIn.objects.create(email=self.user.email)
        Transaction.objects.create(owner=self.user, kind="income", amount="80.00", date=now.date())
        before = list(Transaction.objects.values())
        response = self.client.get(self.link(), follow=True)
        form_url = response.request["PATH_INFO"]
        self.assertTrue(form_url.endswith("/set-password/"))
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "New password")
        response = self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}, follow=True)
        self.assertContains(response, "Your password has been reset.")
        self.assertContains(response, f'href="{reverse("sign_in")}"')
        self.assertNotIn("_password_reset_token", self.client.session)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(list(Transaction.objects.values()), before)
        self.assertEqual(LoginAttempt.objects.get(email=self.user.email).failed_count, 0)
        self.assertFalse(FailedSignIn.objects.filter(email=self.user.email).exists())
        for client in sessions:
            self.assertEqual(client.get(reverse("dashboard")).status_code, 302)
        self.assertContains(self.client.post(reverse("sign_in"), {"email": self.user.email, "password": OLD_PASSWORD}),
                            "Email or password is incorrect")
        self.assertRedirects(self.client.post(reverse("sign_in"), {"email": self.user.email, "password": NEW_PASSWORD}),
                             reverse("dashboard"))

    def test_invalid_expired_used_and_ineligible_links_never_change_password(self):
        issued = datetime(2026, 10, 28, 12)
        with patch.object(default_token_generator, "_now", return_value=issued):
            expired = self.link()
        self.assertContains(self.client.get(expired), EXPIRED)
        for uid, token in [("%%%", "bad"), ("OTk5OTk5", "bad"), ("MQ", "<script>")]:
            response = self.client.get(reverse("accounts:reset_password", kwargs={"uidb64": uid, "token": token}))
            self.assertContains(response, EXPIRED)
            self.assertNotContains(response, '<form method="post">')
        link = self.link()
        form_url = self.client.get(link).url
        # Expiry is rechecked at POST, including a previously opened form.
        with patch.object(default_token_generator, "_now", return_value=datetime.now() + timedelta(hours=1)):
            self.assertContains(self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}), EXPIRED)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))
        self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
        self.assertContains(self.client.get(link), EXPIRED)
        self.assertContains(self.client.post(form_url, {"new_password1": OLD_PASSWORD, "new_password2": OLD_PASSWORD}), EXPIRED)
        for inactive in [True, False]:
            link = self.link()
            if inactive:
                self.user.is_active = False
            else:
                self.user.is_active = True
                self.user.set_unusable_password()
            self.user.save()
            self.assertContains(self.client.get(link), EXPIRED)

    def test_password_validation_and_atomic_recheck_errors_are_displayed(self):
        form_url = self.client.get(self.link()).url
        for password, confirmation, message in [("short", "short", "too short"),
                                                 (NEW_PASSWORD, "different", "didn’t match"),
                                                 ("123456789", "123456789", "entirely numeric")]:
            response = self.client.post(form_url, {"new_password1": password, "new_password2": confirmation})
            self.assertContains(response, message)
        with patch("accounts.recovery.complete_password_reset", side_effect=ValidationError({"new_password1": ["Try another password."]})):
            self.assertContains(self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}),
                                "Try another password.")
        with patch("accounts.recovery.complete_password_reset", side_effect=signing.BadSignature):
            self.assertContains(self.client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}), EXPIRED)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_csrf_and_http_method_guards(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.request_url, {"email": self.user.email}).status_code, 403)
        form_url = client.get(self.link()).url
        self.assertEqual(client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}).status_code, 403)
        client.get(form_url)
        response = client.post(form_url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD,
                                         "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertRedirects(response, reverse("accounts:reset_complete"))
        for url in [self.request_url, form_url, reverse("accounts:reset_sent"), reverse("accounts:reset_complete")]:
            self.assertEqual(self.client.put(url).status_code, 405)
        self.assertEqual(len(mail.outbox), 0)

    def test_source_limit_ignores_forwarded_headers_and_does_not_create_email_keys(self):
        for index in range(30):
            response = self.client.post(self.request_url, {"email": f"unknown{index}@uccs.edu"},
                                        REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR=f"192.0.2.{index}", follow=True)
            self.assertContains(response, CONFIRMATION)
        self.assertEqual(PasswordResetRateLimit.objects.count(), 10)

    def test_global_limit_bounds_distinct_sources_and_addresses_and_expires(self):
        from accounts.models import PasswordResetBudget

        now = timezone.now()
        with patch("accounts.recovery.timezone.now", return_value=now):
            for index in range(120):
                self.client.post(self.request_url, {"email": f"unknown{index}@uccs.edu"}, REMOTE_ADDR=f"192.0.2.{index}")
        self.assertEqual(PasswordResetRateLimit.objects.count(), 100)
        self.assertEqual(PasswordResetBudget.objects.count(), 1)
        budget = PasswordResetBudget.objects.get()
        self.assertEqual(len(budget.admitted_at), 100)
        self.assertNotIn("192.0.2", str(budget.admitted_at))
        with patch("accounts.recovery.timezone.now", return_value=now + timedelta(hours=1)):
            self.client.post(self.request_url, {"email": self.user.email})
        self.assertEqual(PasswordResetRateLimit.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_rolling_source_window_frees_only_expired_admissions(self):
        from accounts.models import PasswordResetBudget

        now = timezone.now()
        for minutes, count in [(0, 1), (59, 9), (60, 2)]:
            with patch("accounts.recovery.timezone.now", return_value=now + timedelta(minutes=minutes)):
                for index in range(count):
                    self.client.post(self.request_url, {"email": f"student{minutes}-{index}@uccs.edu"})
        entries = PasswordResetBudget.objects.get().admitted_at
        self.assertEqual(len(entries), 10)
        self.assertEqual(sum(entry[0] == (now + timedelta(minutes=60)).timestamp() for entry in entries), 1)


@skipUnless(connection.vendor == "postgresql" or (
    connection.vendor == "sqlite" and connection.settings_dict["TEST"].get("NAME")
    and "memory" not in str(connection.settings_dict["TEST"]["NAME"])
), "Concurrency test requires PostgreSQL or file-backed SQLite")
@override_settings(MAILERS=MAILERS)
class RecoveryAdmissionConcurrencyTests(TransactionTestCase):
    def test_concurrent_distinct_addresses_respect_source_and_global_budgets(self):
        from accounts.models import PasswordResetBudget
        from accounts.recovery import claim_recovery_request

        url = reverse("accounts:forgot_password")
        now = timezone.now()
        for state in ["new", "source", "global", "expired"]:
            with self.subTest(state=state):
                PasswordResetBudget.objects.all().delete()
                PasswordResetRateLimit.objects.all().delete()
                when = now - timedelta(hours=1) if state == "expired" else now
                with patch("accounts.recovery.timezone.now", return_value=when):
                    if state in {"source", "expired"}:
                        for _ in range(9):
                            claim_recovery_request("192.0.2.1")
                    if state == "global":
                        for index in range(96):
                            claim_recovery_request(f"198.51.100.{index}")
                workers = 12
                barrier = Barrier(workers)

                def submit(index):
                    close_old_connections()
                    try:
                        barrier.wait(timeout=10)
                        source = f"192.0.2.{index}" if state == "global" else "192.0.2.1"
                        response = Client().post(url, {"email": f"unknown{index}@uccs.edu"}, REMOTE_ADDR=source)
                        return response.status_code, response.url
                    finally:
                        connections.close_all()

                with patch("accounts.recovery.timezone.now", return_value=now), ThreadPoolExecutor(max_workers=workers) as executor:
                    results = list(executor.map(submit, range(workers)))
                self.assertEqual(results, [(302, reverse("accounts:reset_sent"))] * workers)
                expected = {"new": 10, "source": 1, "global": 4, "expired": 10}[state]
                self.assertEqual(PasswordResetRateLimit.objects.count(), expected)
                self.assertEqual(PasswordResetBudget.objects.count(), 1)
