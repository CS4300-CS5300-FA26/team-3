from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.identity import create_verified_user


PASSWORD = "A-tide-of-bright-copper-42!"


@override_settings(MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}},
                   SIGNUP_BASE_URL="https://budget-wise.dev", DEFAULT_FROM_EMAIL="signup@example.com")
class SignupTests(TestCase):
    def submit(self, email="student@example.com", **extra):
        return self.client.post(reverse("accounts:signup"), {"email": email}, **extra)

    @override_settings(ALLOWED_HOSTS=["hostile.example", "testserver"])
    def test_new_address_receives_trusted_link_then_completes_registration(self):
        page = self.client.get(reverse("accounts:signup"))
        self.assertContains(page, 'autocomplete="email"')
        self.assertEqual(list(page.context["form"].fields), ["email"])
        response = self.submit(" Student@OtherDomain.org ", HTTP_HOST="hostile.example")
        self.assertRedirects(response, reverse("accounts:check_email"))
        self.assertContains(self.client.get(response.url), "Check your email")
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["student@otherdomain.org"])
        self.assertEqual(message.from_email, "signup@example.com")
        link = next(line for line in message.body.splitlines() if line.startswith("https://"))
        self.assertTrue(link.startswith("https://budget-wise.dev/accounts/verify/"))
        self.assertIn("24 hours", message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn(f'href="{link}"', html)
        self.assertIn("Set your password</a>", html)
        url = link.removeprefix("https://budget-wise.dev")
        self.assertContains(self.client.get(url), "Set your password")
        self.assertRedirects(self.client.post(url, {"password": PASSWORD,
                              "password_confirmation": PASSWORD}), reverse("accounts:created"))
        self.assertTrue(get_user_model().objects.get().check_password(PASSWORD))
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_URL="/sign-in/")
    def test_existing_owner_notice_has_same_public_response(self):
        create_verified_user("existing@example.com", PASSWORD)
        # Legacy/direct saves are equivalent under the foundation's SQL index.
        get_user_model().objects.update(email="  Existing@Example.COM.  ")
        new = self.submit()
        existing = self.submit("EXISTING@example.com")
        self.assertEqual(new.status_code, existing.status_code)
        self.assertEqual(new.url, existing.url)
        self.assertEqual(self.client.get(new.url).content, self.client.get(existing.url).content)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("already exists", mail.outbox[1].body)
        self.assertNotIn("/verify/", mail.outbox[1].body)
        self.assertIn("https://budget-wise.dev/sign-in/", mail.outbox[1].body)
        html, mimetype = mail.outbox[1].alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn('href="https://budget-wise.dev/sign-in/"', html)
        self.assertIn("Sign in</a>", html)
        self.assertNotIn("/verify/", html)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_invalid_input_and_csrf_never_send(self):
        for email, error in [("bad", "valid email"), ("student@example.com\n", "valid email"),
                             ("a" * 151 + "@example.com", "at most 150 characters")]:
            self.assertContains(self.submit(email), error)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("accounts:signup"), {"email": "a@example.com"}).status_code, 403)
        page = client.get(reverse("accounts:signup"))
        self.assertEqual(client.post(reverse("accounts:signup"), {"email": "a@example.com",
                         "csrfmiddlewaretoken": page.cookies["csrftoken"].value}).status_code, 302)
        self.assertEqual(self.client.put(reverse("accounts:signup")).status_code, 405)
        self.assertEqual(len(mail.outbox), 1)

    def test_recipient_limit_is_shared_across_clients_and_addresses_are_hashed(self):
        from accounts.models import SignupRateLimit

        self.submit("Student@example.com", REMOTE_ADDR="192.0.2.1")
        other = Client()
        response = other.post(reverse("accounts:signup"), {"email": "student@EXAMPLE.com"},
                              REMOTE_ADDR="192.0.2.2")
        self.assertRedirects(response, reverse("accounts:check_email"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(SignupRateLimit.objects.count(), 3)
        for key in SignupRateLimit.objects.values_list("key", flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn("student", key)
            self.assertNotIn("192.0.2", key)

    def test_ip_budget_counts_recipient_throttles_and_ignores_forwarded_header(self):
        for number in range(10):
            self.submit(HTTP_X_FORWARDED_FOR=f"192.0.2.{number}")
        self.submit("different@example.com", HTTP_X_FORWARDED_FOR="198.51.100.1")
        self.assertEqual(len(mail.outbox), 1)
        self.submit("different@example.com", REMOTE_ADDR="192.0.2.2")
        self.assertEqual(len(mail.outbox), 2)

    def test_expired_limits_allow_retry(self):
        from accounts.models import SignupRateLimit

        self.submit()
        SignupRateLimit.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.submit()
        self.assertEqual(len(mail.outbox), 2)

    def test_transport_failure_is_identical_for_new_and_existing_and_consumes_budget(self):
        create_verified_user("existing@example.com", PASSWORD)
        for exception in [SMTPException("secret address/token"), OSError("private transport detail")]:
            with patch("accounts.mail.send_mail", side_effect=exception) as sender:
                new = self.submit("new@example.com", REMOTE_ADDR="192.0.2.1")
                existing = self.submit("existing@example.com", REMOTE_ADDR="192.0.2.2")
                self.assertContains(new, "Unable to send email right now")
                self.assertContains(existing, "Unable to send email right now")
                self.assertNotContains(new, "secret")
                self.assertEqual(sender.call_count, 2)
                self.assertEqual(self.submit("new@example.com").status_code, 302)
            from accounts.models import SignupRateLimit
            SignupRateLimit.objects.all().delete()

    def test_cleanup_keeps_boundary_and_recent_consumed_tokens(self):
        from accounts.models import UsedVerificationToken
        from accounts.verification import VERIFICATION_MAX_AGE

        now = timezone.now()
        boundary = now - timedelta(seconds=VERIFICATION_MAX_AGE)
        for name, consumed in [("old", boundary - timedelta(microseconds=1)),
                               ("boundary", boundary), ("recent", now)]:
            UsedVerificationToken.objects.create(digest=name, consumed_at=consumed)
        with patch("accounts.signup.timezone.now", return_value=now):
            self.submit()
        self.assertSetEqual(set(UsedVerificationToken.objects.values_list("digest", flat=True)),
                            {"boundary", "recent"})
