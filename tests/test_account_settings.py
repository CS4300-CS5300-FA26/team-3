"""Increment 1: account actions, shared navigation and generic missing pages."""
from datetime import date
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import LowBalanceThreshold, PasswordResetRateLimit
from accounts.password_reset_requests import RESET_CONFIRMATION
from transactions.models import Transaction


ACCOUNT_RESET_FEEDBACK = "Password reset requested. Check your email for instructions."


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}})
class AccountSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@example.com", email="student@example.com", password="Local-test-password-42!",
        )
        self.client.force_login(self.user)
        self.url = "/account/"

    def test_read_only_email_and_dashboard_actions(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.user.email)
        self.assertNotContains(response, 'name="email"')
        dashboard = self.client.get(reverse("dashboard"))
        self.assertNotContains(dashboard, 'name="amount"')
        self.assertEqual(self.client.post(reverse("dashboard"), {"amount": "5"}).status_code, 405)
        for route in ("record_income", "record_expense"):
            self.assertContains(dashboard, f'href="{reverse(route)}"', count=1)
        for route in ("dashboard", "record_income", "record_expense", "spending_by_category"):
            response = self.client.get(reverse(route))
            self.assertContains(response, 'href="/account/"', count=1)
            self.assertContains(response, f'action="{reverse("sign_out")}"', count=1)

    @override_settings(DEBUG=False)
    def test_dashboard_navigation_is_visible_only_signed_in_away_from_dashboard(self):
        link = f'<a href="{reverse("dashboard")}">Dashboard</a>'
        record = Transaction.objects.create(
            owner=self.user, kind="income", amount="5.00", date=date(2026, 11, 1),
            description="Navigation check",
        )
        for path in (
            self.url, reverse("record_income"), reverse("record_expense"),
            reverse("spending_by_category"), reverse("edit_transaction", args=[record.pk]),
            reverse("delete_transaction", args=[record.pk]), "/missing-navigation-page/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, link, count=1, html=True,
                                    status_code=404 if path.startswith("/missing") else 200)
        for path in ("/", reverse("dashboard"), reverse("dashboard") + "?month=2026-10"):
            with self.subTest(path=path):
                self.assertNotContains(self.client.get(path), link, html=True)
        self.client.logout()
        for path in (reverse("sign_in"), reverse("accounts:forgot_password"), "/missing-navigation-page/"):
            with self.subTest(anonymous_path=path):
                self.assertNotContains(self.client.get(path), link, html=True,
                                       status_code=404 if path.startswith("/missing") else 200)

    def test_settings_and_actions_require_login_and_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        for data in ({"amount": "0"}, {"action": "reset_password"}):
            self.assertEqual(csrf_client.post(self.url, data).status_code, 403)
        self.assertFalse(LowBalanceThreshold.objects.exists())
        self.assertFalse(PasswordResetRateLimit.objects.exists())
        self.client.logout()
        for method in (self.client.get, self.client.post):
            self.assertRedirects(method(self.url), reverse("sign_in") + "?next=/account/")

    def test_account_confirmation_acknowledges_request_without_public_lookup_wording(self):
        response = self.client.post(self.url, {"action": "reset_password"}, follow=True)
        self.assertContains(response, ACCOUNT_RESET_FEEDBACK)
        self.assertNotContains(response, RESET_CONFIRMATION)
        public = self.client.post(reverse("accounts:forgot_password"), {
            "email": "unknown@example.com",
        }, follow=True)
        self.assertContains(public, RESET_CONFIRMATION)
        self.assertNotContains(public, ACCOUNT_RESET_FEEDBACK)

    def test_reset_uses_session_identity_and_shared_per_email_budget(self):
        for _ in range(3):
            self.client.post(reverse("accounts:forgot_password"), {"email": self.user.email})
        for _ in range(3):
            response = self.client.post(self.url, {"action": "reset_password", "email": "other@example.com"}, follow=True)
            self.assertContains(response, ACCOUNT_RESET_FEEDBACK)
        self.assertEqual(len(mail.outbox), 5)
        self.assertTrue(all(message.to == [self.user.email] for message in mail.outbox))
        self.assertEqual(len(PasswordResetRateLimit.objects.get().admitted_at), 5)
        self.assertNotIn(ACCOUNT_RESET_FEEDBACK, self.client.get(self.url).content.decode())

    def test_reset_shares_source_and_global_admission_with_public_recovery(self):
        from accounts.models import PasswordResetBudget
        from accounts.recovery import claim_recovery_request

        for mode in ("source", "global"):
            with self.subTest(mode=mode):
                PasswordResetBudget.objects.all().delete()
                for i in range(10 if mode == "source" else 100):
                    claim_recovery_request("127.0.0.1" if mode == "source" else f"192.0.2.{i}")
                with patch("accounts.recovery.request_password_reset") as send:
                    response = self.client.post(self.url, {"action": "reset_password"}, follow=True)
                send.assert_not_called()
                self.assertContains(response, ACCOUNT_RESET_FEEDBACK)

    def test_transport_failure_is_neutral_and_does_not_change_password_or_threshold(self):
        LowBalanceThreshold.objects.create(owner=self.user, amount="12.34")
        old_password = self.user.password
        with patch("accounts.password_reset_requests.send_account_email", side_effect=SMTPException("private")):
            response = self.client.post(self.url, {"action": "reset_password"}, follow=True)
        self.assertContains(response, ACCOUNT_RESET_FEEDBACK)
        self.assertNotContains(response, "private")
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)
        self.assertEqual(str(LowBalanceThreshold.objects.get(owner=self.user).amount), "12.34")
        self.assertIn("no-store", response["Cache-Control"])

    def test_zero_and_invalid_threshold_preserve_saved_value(self):
        response = self.client.post(self.url, {"amount": "0"}, follow=True)
        self.assertContains(response, "Safety threshold saved.")
        for amount in ("", "-1", "1.001", "10000000000", "NaN"):
            with self.subTest(amount=amount):
                response = self.client.post(self.url, {"amount": amount})
                self.assertTrue(response.context["threshold_form"].errors)
                self.assertEqual(LowBalanceThreshold.objects.get(owner=self.user).amount, 0)
        self.assertEqual(self.client.post(self.url, {"action": "unknown"}).status_code, 400)


@override_settings(DEBUG=False)
class MissingPageTests(TestCase):
    def test_unknown_urls_are_generic_for_both_sessions(self):
        user = get_user_model().objects.create_user(username="student")
        for authenticated in (False, True):
            if authenticated:
                self.client.force_login(user)
            for path in ("/not-a-page/", "/accounts/not-a-page/", "/not-a-page"):
                with self.subTest(authenticated=authenticated, path=path):
                    response = self.client.get(path)
                    self.assertContains(response, "Page not found", status_code=404)
                    self.assertNotContains(response, path, status_code=404)
                    self.assertContains(response, "Back to dashboard" if authenticated else "Go to sign in", status_code=404)

    def test_missing_and_other_user_records_have_same_generic_response(self):
        user = get_user_model().objects.create_user(username="student")
        other = get_user_model().objects.create_user(username="other")
        record = Transaction.objects.create(owner=other, kind="income", amount="5", date=date(2026, 10, 1), description="Private record")
        self.client.force_login(user)
        for route in ("edit_transaction", "delete_transaction"):
            for method in (self.client.get, self.client.post):
                missing = method(reverse(route, args=[record.pk + 1]))
                foreign = method(reverse(route, args=[record.pk]))
                self.assertEqual(missing.status_code, 404)
                self.assertEqual(foreign.status_code, 404)
                self.assertContains(foreign, "Page not found", status_code=404)
                self.assertNotContains(foreign, "Private record", status_code=404)
        self.assertTrue(Transaction.objects.filter(pk=record.pk).exists())

    def test_valid_private_public_and_slash_routes_keep_their_behavior(self):
        for route in ("dashboard", "account_settings", "record_income", "record_expense"):
            url = reverse(route)
            self.assertRedirects(self.client.get(url.rstrip("/")), reverse("sign_in") + "?next=" + url.rstrip("/"))
        for route in ("sign_in", "accounts:forgot_password", "accounts:reset_sent", "accounts:reset_complete"):
            url = reverse(route)
            self.assertRedirects(self.client.get(url.rstrip("/")), url, status_code=301)
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
