"""D12 core: real Django tokens, password validation, sessions and database writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import OperationalError, close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.views.debug import SafeExceptionReporterFilter

from accounts.identity import create_verified_user
from accounts.models import FailedSignIn, LoginAttempt
from accounts.verification import issue_verification_token
from transactions.models import Transaction


OLD_PASSWORD = "A-tide-of-bright-copper-42!"
NEW_PASSWORD = "Another-wave-of-silver-73!"
ISSUED_AT = datetime(2026, 10, 28, 12)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = create_verified_user("student@uccs.edu", OLD_PASSWORD)
        self.token = default_token_generator.make_token(self.user)

    def reset(self, token=None, password=NEW_PASSWORD, confirmation=NEW_PASSWORD, user_id=None):
        from accounts.password_reset import complete_password_reset

        return complete_password_reset(
            self.user.pk if user_id is None else user_id,
            self.token if token is None else token, password, confirmation,
        )

    def lock_account(self, user):
        now = timezone.now()
        LoginAttempt.objects.create(
            email=user.email, failed_count=5, first_failed_at=now,
            blocked_until=now + timedelta(minutes=15),
        )
        FailedSignIn.objects.bulk_create([FailedSignIn(email=user.email) for _ in range(5)])

    def test_token_lifetime_is_exactly_thirty_minutes(self):
        with patch.object(default_token_generator, "_now", return_value=ISSUED_AT):
            token = default_token_generator.make_token(self.user)
        for seconds, valid in [(1799, True), (1800, True), (1801, False)]:
            with self.subTest(seconds=seconds), patch.object(
                default_token_generator, "_now", return_value=ISSUED_AT + timedelta(seconds=seconds),
            ):
                self.assertEqual(default_token_generator.check_token(self.user, token), valid)

    def test_reset_restores_signin_and_preserves_budget_and_other_accounts(self):
        other = create_verified_user("other@uccs.edu", OLD_PASSWORD)
        self.lock_account(self.user)
        self.lock_account(other)
        Transaction.objects.create(
            owner=self.user, kind="income", amount="80.00", date="2026-10-28",
            description="Paycheck",
        )
        transactions_before = list(Transaction.objects.values())
        identity_before = get_user_model().objects.values().get(pk=self.user.pk)
        self.reset()
        identity_after = get_user_model().objects.values().get(pk=self.user.pk)
        self.assertNotEqual(identity_before.pop("password"), identity_after.pop("password"))
        self.assertEqual(identity_before, identity_after)
        self.assertEqual(list(Transaction.objects.values()), transactions_before)
        attempt = LoginAttempt.objects.get(email=self.user.email)
        self.assertEqual(attempt.failed_count, 0)
        self.assertIsNone(attempt.first_failed_at)
        self.assertIsNone(attempt.blocked_until)
        self.assertFalse(FailedSignIn.objects.filter(email=self.user.email).exists())
        self.assertEqual(LoginAttempt.objects.get(email=other.email).failed_count, 5)
        self.assertEqual(FailedSignIn.objects.filter(email=other.email).count(), 5)
        other.refresh_from_db()
        self.assertTrue(other.check_password(OLD_PASSWORD))

        response = self.client.post(reverse("sign_in"), {"email": self.user.email, "password": OLD_PASSWORD})
        self.assertContains(response, "Email or password is incorrect")
        response = self.client.post(reverse("sign_in"), {"email": self.user.email, "password": NEW_PASSWORD})
        self.assertRedirects(response, reverse("dashboard"))
        dashboard = self.client.get(reverse("dashboard"), {"month": "2026-10-01"})
        self.assertEqual(dashboard.context["remaining_budget"], Decimal("80.00"))

    def test_reset_invalidates_two_existing_sessions_but_not_another_users(self):
        other = create_verified_user("other@uccs.edu", OLD_PASSWORD)
        sessions = [Client(), Client()]
        other_session = Client()
        for client in sessions:
            client.force_login(self.user)
            self.assertEqual(client.get(reverse("dashboard")).status_code, 200)
        other_session.force_login(other)
        # Signing in changes last_login, so issue the token after those sessions exist.
        self.user.refresh_from_db()
        self.token = default_token_generator.make_token(self.user)
        self.reset()
        for client in sessions:
            self.assertRedirects(client.get(reverse("dashboard")), reverse("sign_in") + "?next=/dashboard/")
        self.assertEqual(other_session.get(reverse("dashboard")).status_code, 200)

    def test_invalid_passwords_leave_password_lockout_and_token_unchanged(self):
        self.lock_account(self.user)
        for password, confirmation in [
            (NEW_PASSWORD, "different"), ("Ab3!xyz", "Ab3!xyz"),
            ("password", "password"), ("123456789", "123456789"),
            ("student@uccs.edu", "student@uccs.edu"), ("", ""),
        ]:
            with self.subTest(password=password), self.assertRaises(ValidationError):
                self.reset(password=password, confirmation=confirmation)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password(OLD_PASSWORD))
            self.assertTrue(default_token_generator.check_token(self.user, self.token))
            self.assertEqual(LoginAttempt.objects.get(email=self.user.email).failed_count, 5)
            self.assertEqual(FailedSignIn.objects.filter(email=self.user.email).count(), 5)
        # Exactly eight characters is allowed if the configured validators accept it.
        self.reset(password="K8!vR2@q", confirmation="K8!vR2@q")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("K8!vR2@q"))

    def test_invalid_wrong_account_and_signup_tokens_are_rejected(self):
        other = create_verified_user("other@uccs.edu", OLD_PASSWORD)
        tokens = ["", "bad", self.token + "x", default_token_generator.make_token(other),
                  issue_verification_token(self.user.email)]
        for token in tokens:
            with self.subTest(token=token), self.assertRaises(signing.BadSignature):
                self.reset(token=token)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))
        self.assertFalse(LoginAttempt.objects.exists())

    def test_expired_token_cannot_change_password_or_clear_lockout(self):
        self.lock_account(self.user)
        with patch.object(default_token_generator, "_now", return_value=ISSUED_AT):
            self.token = default_token_generator.make_token(self.user)
        with patch.object(default_token_generator, "_now", return_value=ISSUED_AT + timedelta(seconds=1801)):
            with self.assertRaises(signing.BadSignature):
                self.reset()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))
        self.assertEqual(LoginAttempt.objects.get(email=self.user.email).failed_count, 5)

    def test_all_outstanding_tokens_are_invalid_after_reset_even_to_same_password(self):
        with patch.object(default_token_generator, "_now", return_value=ISSUED_AT):
            first = default_token_generator.make_token(self.user)
        with patch.object(default_token_generator, "_now", return_value=ISSUED_AT + timedelta(seconds=1)):
            second = default_token_generator.make_token(self.user)
            self.assertTrue(default_token_generator.check_token(self.user, first))
            self.reset(token=second, password=OLD_PASSWORD, confirmation=OLD_PASSWORD)
            for token in [first, second]:
                with self.assertRaises(signing.BadSignature):
                    self.reset(token=token)

    def test_deleted_inactive_and_unusable_password_accounts_are_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(signing.BadSignature):
            self.reset()
        self.user.is_active = True
        self.user.set_unusable_password()
        self.user.save()
        self.token = default_token_generator.make_token(self.user)
        with self.assertRaises(signing.BadSignature):
            self.reset()
        user_id = self.user.pk
        self.user.delete()
        with self.assertRaises(signing.BadSignature):
            self.reset(user_id=user_id)
        self.assertFalse(LoginAttempt.objects.exists())

    def test_database_failure_rolls_back_password_and_lockout_changes(self):
        from django.db.models.query import QuerySet

        self.lock_account(self.user)
        original_delete = QuerySet.delete

        def fail_cleanup(queryset):
            if queryset.model is FailedSignIn:
                raise OperationalError("unavailable")
            return original_delete(queryset)

        with patch.object(QuerySet, "delete", fail_cleanup), self.assertRaises(OperationalError):
            self.reset()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))
        self.assertEqual(LoginAttempt.objects.get(email=self.user.email).failed_count, 5)
        self.assertEqual(FailedSignIn.objects.filter(email=self.user.email).count(), 5)
        self.reset()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_account_disappearing_during_reset_is_an_invalid_link(self):
        from django.db.models.query import QuerySet

        original_get = QuerySet.get

        def disappearing_user(queryset, *args, **kwargs):
            if queryset.model is get_user_model() and queryset.query.select_for_update:
                raise get_user_model().DoesNotExist
            return original_get(queryset, *args, **kwargs)

        with patch.object(QuerySet, "get", disappearing_user), self.assertRaises(signing.BadSignature):
            self.reset()
        self.assertFalse(LoginAttempt.objects.exists())

    def test_account_without_a_valid_email_is_an_invalid_link(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])
        self.token = default_token_generator.make_token(self.user)
        with self.assertRaises(signing.BadSignature):
            self.reset()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))
        self.assertFalse(LoginAttempt.objects.exists())

    @override_settings(DEBUG=False)
    def test_database_exception_reports_redact_reset_credentials(self):
        from accounts.password_reset import complete_password_reset

        with patch.object(get_user_model(), "save", side_effect=OperationalError("unavailable")):
            try:
                complete_password_reset(self.user.pk, self.token, NEW_PASSWORD, NEW_PASSWORD)
            except OperationalError as error:
                reporter = SafeExceptionReporterFilter()
                # Skip this test's caller frame; inspect the helper and its callees.
                traceback = error.__traceback__.tb_next
                while traceback:
                    variables = repr(list(reporter.get_traceback_frame_variables(None, traceback.tb_frame)))
                    self.assertNotIn(self.token, variables)
                    self.assertNotIn(NEW_PASSWORD, variables)
                    traceback = traceback.tb_next
            else:
                self.fail("Expected database failure")


@skipUnless(
    connection.vendor == "postgresql" or (
        connection.vendor == "sqlite"
        and connection.settings_dict["TEST"].get("NAME")
        and "memory" not in str(connection.settings_dict["TEST"]["NAME"])
    ),
    "Concurrency test requires PostgreSQL or file-backed SQLite",
)
class PasswordResetConcurrencyTests(TransactionTestCase):
    def test_concurrent_submissions_of_one_token_have_only_one_winner(self):
        from accounts.password_reset import complete_password_reset

        user = create_verified_user("student@uccs.edu", OLD_PASSWORD)
        token = default_token_generator.make_token(user)
        barrier = Barrier(2)

        def reset(password):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                complete_password_reset(user.pk, token, password, password)
                return password
            except signing.BadSignature:
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(reset, [NEW_PASSWORD, NEW_PASSWORD + "different"]))
        winners = [password for password in results if password is not None]
        self.assertEqual(len(winners), 1)
        user.refresh_from_db()
        self.assertTrue(user.check_password(winners[0]))
