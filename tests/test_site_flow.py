"""D1/D2 integration: real routes, isolated data, and recoverable navigation."""
from datetime import date
from urllib.parse import urlsplit

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.identity import create_verified_user
from accounts.models import UsedVerificationToken
from accounts.verification import issue_verification_token
from transactions.models import Transaction


PASSWORD = "Copper-tide-with-bright-clouds-42!"


@override_settings(MAILERS={"default": {
    "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
}})
class SiteFlowTests(TestCase):
    def test_anonymous_urls_require_login_except_registration_and_admin_login(self):
        for path in ["/", "/dashboard/", "/income/", "/expense/", "/sign-out/", "/not-a-page/", "/accounts/not-a-page/"]:
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.request["PATH_INFO"], reverse("sign_in"))
                self.assertContains(response, 'href="' + reverse("accounts:signup") + '"')
                self.assertNotContains(response, "Demo budget")
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_signed_in_visitor_cannot_register_a_different_account(self):
        from django.contrib.auth import get_user_model

        user = create_verified_user("current@example.com", PASSWORD)
        self.client.force_login(user)
        url = reverse("accounts:verify", args=[issue_verification_token("new@example.com")])
        for response in [self.client.get(url), self.client.post(url, {
            "password": PASSWORD, "password_confirmation": PASSWORD,
        })]:
            self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(UsedVerificationToken.objects.exists())

    def test_protected_routes_reach_signin_and_resume_the_requested_page(self):
        create_verified_user("student@example.com", PASSWORD)
        for route in ["dashboard", "record_income", "record_expense"]:
            with self.subTest(route=route):
                self.client.logout()
                destination = reverse(route)
                response = self.client.get(destination)
                self.assertRedirects(response, reverse("sign_in") + "?next=" + destination)
                response = self.client.post(response.url, {
                    "email": " STUDENT@example.com ", "password": PASSWORD,
                })
                self.assertRedirects(response, destination)

    def test_login_rejects_external_redirects_and_signed_in_auth_pages_return_home(self):
        create_verified_user("student@example.com", PASSWORD)
        for destination in ["https://evil.example/", "//evil.example/", "/sign-in/"]:
            with self.subTest(destination=destination):
                self.client.logout()
                response = self.client.post(reverse("sign_in"), {
                    "email": "student@example.com", "password": PASSWORD, "next": destination,
                })
                self.assertRedirects(response, reverse("dashboard"))
        for route in ["sign_in", "accounts:signup"]:
            self.assertRedirects(self.client.get(reverse(route)), reverse("dashboard"))

    def test_public_pages_link_to_signup_and_signin(self):
        for route in ["sign_in", "accounts:signup", "accounts:check_email", "accounts:created"]:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertContains(response, 'href="' + reverse("sign_in") + '"')
                self.assertContains(response, 'href="' + reverse("accounts:signup") + '"')
                without_slash = self.client.get(reverse(route).rstrip("/"), follow=True)
                self.assertEqual(without_slash.request["PATH_INFO"], reverse(route))

    def test_signup_signin_record_and_signout_with_csrf(self):
        self.client = Client(enforce_csrf_checks=True)

        def post(url, data):
            self.client.get(url)
            return self.client.post(url, {**data, "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value})

        self.assertRedirects(post(reverse("accounts:signup"), {"email": "student@example.com"}), reverse("accounts:check_email"))
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("https://"))
        self.assertRedirects(post(urlsplit(link).path, {
            "password": PASSWORD, "password_confirmation": PASSWORD,
        }), reverse("accounts:created"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(post(reverse("sign_in"), {
            "email": "student@example.com", "password": PASSWORD,
        }), reverse("dashboard"))
        other = create_verified_user("other@example.com", PASSWORD)
        Transaction.objects.create(owner=other, kind="income", amount="55.00",
                                   date=date(2026, 10, 22), description="Private other income")
        for route, data in [
            ("record_income", {"amount": "123.45", "date": "2026-10-22", "description": "My paycheck"}),
            ("record_expense", {"amount": "12.34", "date": "2026-10-22", "description": "My lunch", "category": "Food", "is_fixed": "variable"}),
        ]:
            self.assertRedirects(post(reverse(route), data), reverse(route))
            response = self.client.get(reverse(route))
            self.assertContains(response, 'href="' + reverse("dashboard") + '"')
        dashboard = self.client.get(reverse("dashboard"), {"month": "2026-10"})
        self.assertContains(dashboard, "My paycheck")
        self.assertContains(dashboard, "My lunch")
        self.assertNotContains(dashboard, "Private other income")
        # Logout must be a real CSRF-protected POST, never a navigable GET.
        self.assertEqual(self.client.get(reverse("sign_out")).status_code, 405)
        self.assertEqual(self.client.post(reverse("sign_out")).status_code, 403)
        response = self.client.post(reverse("sign_out"), {
            "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, reverse("sign_in"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("sign_in") + "?next=/dashboard/")
