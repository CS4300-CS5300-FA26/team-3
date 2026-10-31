"""Issue #23 request service: delivery, rolling admissions and worker races."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as datetime_timezone
from smtplib import SMTPException
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import resolve
from django.utils.http import urlsafe_base64_decode
from django.views.debug import SafeExceptionReporterFilter

from accounts.identity import create_verified_user
from accounts.models import FailedSignIn, LoginAttempt


PASSWORD = "A-tide-of-bright-copper-42!"
CONFIRMATION = "If an account matches, password reset instructions will be sent"
NOW = datetime(2026, 10, 29, 12, tzinfo=datetime_timezone.utc)
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


def request_reset(email="student@uccs.edu"):
    from accounts.password_reset_requests import request_password_reset

    return request_password_reset(email)


def sent_credentials(message):
    link = next(line for line in message.body.splitlines() if line.startswith("https://"))
    match = resolve(link.removeprefix("https://budget-wise.dev"))
    return link, int(urlsafe_base64_decode(match.kwargs["uidb64"])), match.kwargs["token"]


@override_settings(ROOT_URLCONF="tests.reset_urls", MAILERS=MAILERS,
                   SIGNUP_BASE_URL="https://budget-wise.dev", DEFAULT_FROM_EMAIL="accounts@example.com")
class PasswordResetRequestTests(TestCase):
    def setUp(self):
        self.user = create_verified_user("student@uccs.edu", PASSWORD)

    def test_known_email_gets_styled_trusted_link_and_core_accepts_it(self):
        from accounts.password_reset import complete_password_reset

        self.assertEqual(request_reset(" Student@UCCS.EDU. "), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        link, user_id, token = sent_credentials(message)
        self.assertEqual(user_id, self.user.pk)
        self.assertEqual(message.to, [self.user.email])
        self.assertEqual(message.from_email, "accounts@example.com")
        self.assertEqual(message.subject, "Reset your BudgetWise password")
        self.assertIn("30 minutes", message.body)
        self.assertIn("ignore this email", message.body)
        self.assertIn(f'href="{link}"', message.alternatives[0].content)
        self.assertIn("Reset your password</a>", message.alternatives[0].content)
        complete_password_reset(user_id, token, PASSWORD + "new", PASSWORD + "new")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD + "new"))

    def test_legacy_address_matches_and_only_that_account_receives_mail(self):
        get_user_model().objects.filter(pk=self.user.pk).update(email="  Student@UCCS.EDU.  ")
        create_verified_user("other@uccs.edu", PASSWORD)
        request_reset()
        self.assertEqual(mail.outbox[0].to, ["student@uccs.edu"])
        self.assertEqual(sent_credentials(mail.outbox[0])[1], self.user.pk)

    def test_unknown_invalid_inactive_and_unusable_accounts_share_confirmation(self):
        inactive = create_verified_user("inactive@uccs.edu", PASSWORD)
        inactive.is_active = False
        inactive.save()
        unusable = create_verified_user("unusable@uccs.edu", PASSWORD)
        unusable.set_unusable_password()
        unusable.save()
        for email in ["nobody@uccs.edu", inactive.email, unusable.email, "bad", None,
                      "student@uccs.edu\n", "a" * 151 + "@uccs.edu"]:
            with self.subTest(email=email):
                self.assertEqual(request_reset(email), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(get_user_model().objects.count(), 3)

    def test_request_preserves_password_sessions_lockout_and_saved_data(self):
        from transactions.models import Transaction

        self.client.force_login(self.user)
        LoginAttempt.objects.create(email=self.user.email, failed_count=5,
                                    first_failed_at=NOW, blocked_until=NOW + timedelta(minutes=15))
        FailedSignIn.objects.create(email=self.user.email, created_at=NOW)
        Transaction.objects.create(owner=self.user, kind="income", amount="80.00", date="2026-10-29")
        before = [list(model.objects.values()) for model in
                  [get_user_model(), LoginAttempt, FailedSignIn, Transaction]]
        request_reset()
        after = [list(model.objects.values()) for model in
                 [get_user_model(), LoginAttempt, FailedSignIn, Transaction]]
        self.assertEqual(before, after)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_each_link_expires_after_thirty_minutes_and_all_die_on_completion(self):
        from accounts.password_reset import complete_password_reset

        issued = NOW.replace(tzinfo=None)
        with patch.object(default_token_generator, "_now", return_value=issued):
            request_reset()
        with patch.object(default_token_generator, "_now", return_value=issued + timedelta(seconds=1)):
            request_reset()
        tokens = [sent_credentials(message)[2] for message in mail.outbox]
        self.assertNotEqual(*tokens)
        with patch.object(default_token_generator, "_now", return_value=issued + timedelta(seconds=1800)):
            self.assertTrue(all(default_token_generator.check_token(self.user, token) for token in tokens))
        with patch.object(default_token_generator, "_now", return_value=issued + timedelta(seconds=1801)):
            self.assertFalse(default_token_generator.check_token(self.user, tokens[0]))
        with patch.object(default_token_generator, "_now", return_value=issued + timedelta(seconds=2)):
            complete_password_reset(self.user.pk, tokens[0], PASSWORD + "new", PASSWORD + "new")
            self.user.refresh_from_db()
            self.assertFalse(any(default_token_generator.check_token(self.user, token) for token in tokens))

    def test_five_admissions_are_shared_by_normalized_address_but_not_other_addresses(self):
        for email in ["student@uccs.edu", " Student@UCCS.EDU. "] * 3:
            self.assertEqual(request_reset(email), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 5)
        create_verified_user("other@uccs.edu", PASSWORD)
        request_reset("other@uccs.edu")
        self.assertEqual(len(mail.outbox), 6)

    def test_rolling_hour_frees_only_the_admission_that_has_expired(self):
        with patch("accounts.password_reset_requests.timezone.now", return_value=NOW):
            request_reset()
        with patch("accounts.password_reset_requests.timezone.now", return_value=NOW + timedelta(minutes=59)):
            for _ in range(4):
                request_reset()
        with patch("accounts.password_reset_requests.timezone.now", return_value=NOW + timedelta(hours=1) - timedelta(microseconds=1)):
            request_reset()
        self.assertEqual(len(mail.outbox), 5)
        with patch("accounts.password_reset_requests.timezone.now", return_value=NOW + timedelta(hours=1)):
            request_reset()
            request_reset()
        self.assertEqual(len(mail.outbox), 6)

    def test_unknown_requests_spend_budget_even_if_account_is_created_later(self):
        for _ in range(5):
            request_reset("future@uccs.edu")
        create_verified_user("future@uccs.edu", PASSWORD)
        self.assertEqual(request_reset("future@uccs.edu"), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 0)

    def test_transport_failures_are_private_and_still_spend_budget(self):
        with patch("accounts.mail.send_mail", side_effect=SMTPException("private token/address")) as sender:
            for _ in range(6):
                self.assertEqual(request_reset(), CONFIRMATION)
            self.assertEqual(sender.call_count, 5)
        with patch("accounts.mail.send_mail", side_effect=OSError("private detail")):
            create_verified_user("other@uccs.edu", PASSWORD)
            self.assertEqual(request_reset("other@uccs.edu"), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ROOT_URLCONF="budgetwise.urls")
    def test_unmounted_completion_route_never_sends_a_live_link(self):
        self.assertEqual(request_reset(), CONFIRMATION)
        self.assertEqual(len(mail.outbox), 0)

    def test_storage_is_bounded_hashed_and_cleans_expired_addresses(self):
        from accounts.models import PasswordResetRateLimit

        with patch("accounts.password_reset_requests.timezone.now", return_value=NOW):
            for _ in range(10):
                request_reset()
            request_reset("unknown@uccs.edu")
        rows = list(PasswordResetRateLimit.objects.values())
        self.assertEqual(len(rows), 2)
        self.assertNotIn("uccs.edu", str(rows))
        self.assertNotIn(sent_credentials(mail.outbox[0])[2], str(rows))
        self.assertEqual(sorted(len(row["admitted_at"]) for row in rows), [1, 5])
        with patch("accounts.password_reset_requests.timezone.now", return_value=NOW + timedelta(hours=1)):
            request_reset()
        self.assertEqual(PasswordResetRateLimit.objects.count(), 1)
        self.assertEqual(len(PasswordResetRateLimit.objects.get().admitted_at), 1)
        self.assertEqual(len(mail.outbox), 6)

    @override_settings(DEBUG=False)
    def test_unexpected_exception_reports_redact_link_and_email_locals(self):
        captured = []

        def fail_send(*args, **kwargs):
            captured.append(args[1])
            raise RuntimeError("unexpected backend failure")

        with patch("accounts.mail.send_mail", side_effect=fail_send):
            try:
                request_reset()
            except RuntimeError as error:
                token = captured[0].split("/reset/")[1].split("/")[1]
                reporter = SafeExceptionReporterFilter()
                traceback = error.__traceback__
                while traceback and traceback.tb_frame.f_code.co_name != "sensitive_variables_wrapper":
                    traceback = traceback.tb_next
                self.assertIsNotNone(traceback)
                while traceback:
                    variables = repr(list(reporter.get_traceback_frame_variables(None, traceback.tb_frame)))
                    self.assertNotIn(token, variables)
                    self.assertNotIn(self.user.email, variables)
                    traceback = traceback.tb_next
            else:
                self.fail("Unexpected failures must not disappear")


@skipUnless(connection.vendor == "postgresql" or (
    connection.vendor == "sqlite" and connection.settings_dict["TEST"].get("NAME")
    and "memory" not in str(connection.settings_dict["TEST"]["NAME"])
), "Concurrency test requires PostgreSQL or file-backed SQLite")
@override_settings(ROOT_URLCONF="tests.reset_urls", MAILERS=MAILERS)
class PasswordResetRequestConcurrencyTests(TransactionTestCase):
    def test_concurrent_requests_admit_exactly_five_for_new_existing_and_expired_rows(self):
        from accounts.models import PasswordResetRateLimit

        create_verified_user("student@uccs.edu", PASSWORD)
        for state in ["new", "existing", "expired"]:
            with self.subTest(state=state):
                PasswordResetRateLimit.objects.all().delete()
                if state != "new":
                    when = NOW if state == "existing" else NOW - timedelta(hours=1)
                    with patch("accounts.password_reset_requests.timezone.now", return_value=when):
                        request_reset()
                barrier = Barrier(8)

                def submit(index):
                    close_old_connections()
                    try:
                        barrier.wait(timeout=10)
                        return request_reset(" Student@UCCS.edu. " if index % 2 else "student@uccs.edu")
                    finally:
                        connections.close_all()

                with patch("accounts.password_reset_requests.timezone.now", return_value=NOW), patch(
                    "accounts.mail.send_mail", return_value=1,
                ) as sender, ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(submit, range(8)))
                self.assertEqual(results, [CONFIRMATION] * 8)
                self.assertEqual(sender.call_count, 4 if state == "existing" else 5)
                self.assertEqual(len(PasswordResetRateLimit.objects.get().admitted_at), 5)
