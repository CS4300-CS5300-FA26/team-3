from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.verification import issue_verification_token


PASSWORD = "  A-tide-of-bright-copper-42!  "


class RegistrationViewTests(TestCase):
    def setUp(self):
        self.token = issue_verification_token("student@uccs.edu")
        self.url = reverse("accounts:verify", args=[self.token])

    def submit(self, **overrides):
        data = {"password": PASSWORD, "password_confirmation": PASSWORD}
        data.update(overrides)
        return self.client.post(self.url, data)

    @override_settings(LOGIN_URL="/sign-in/")
    def test_get_then_registration_creates_ordinary_user_without_login(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Set your password")
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(page["Referrer-Policy"], "same-origin")
        self.assertContains(page, 'autocomplete="new-password"', count=2)
        response = self.submit(email="attacker@example.com", is_staff="true",
                               is_superuser="true", next="https://evil.example/")
        self.assertRedirects(response, reverse("accounts:created"))
        user = get_user_model().objects.get()
        self.assertEqual(user.username, "student@uccs.edu")
        self.assertEqual(user.email, user.username)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn("_auth_user_id", self.client.session)
        success = self.client.get(response.url)
        self.assertContains(success, "Account created")
        self.assertContains(success, 'href="/sign-in/"')
        self.assertContains(success, "Sign in")
        self.assertNotContains(success, self.token)

    def test_password_errors_allow_retry_without_echoing_password(self):
        for overrides, error in [
            ({"password_confirmation": "different"}, "Passwords do not match."),
            ({"password": "short", "password_confirmation": "short"}, "at least 8 characters"),
            ({"password": ""}, "This field is required."),
        ]:
            with self.subTest(overrides=overrides):
                response = self.submit(**overrides)
                self.assertContains(response, error)
                self.assertNotContains(response, PASSWORD)
                self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(self.submit().status_code, 302)
        self.assertTrue(get_user_model().objects.get().check_password(PASSWORD))

    def test_invalid_and_expired_links_never_create_user(self):
        invalid_url = reverse("accounts:verify", args=[self.token + "x"])
        for method in [self.client.get, self.client.post]:
            response = method(invalid_url, {"password": PASSWORD, "password_confirmation": PASSWORD})
            self.assertContains(response, "This verification link is invalid or no longer available.", status_code=400)
            self.assertNotContains(response, '<form', status_code=400)
        with patch("django.core.signing.time.time", return_value=1000000):
            token = issue_verification_token("student@uccs.edu")
        self.url = reverse("accounts:verify", args=[token])
        with patch("django.core.signing.time.time", return_value=1086401):
            self.assertEqual(self.client.get(self.url).status_code, 400)
            self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_consumed_link_stays_unusable_after_account_deletion(self):
        self.submit()
        for deleted in [False, True]:
            if deleted:
                get_user_model().objects.get().delete()
            with self.subTest(deleted=deleted):
                for response in [self.client.get(self.url), self.submit()]:
                    self.assertContains(response, "This verification link is invalid or no longer available.", status_code=400)
                    self.assertNotContains(response, '<form', status_code=400)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_csrf_is_required_and_supported_methods_are_bounded(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, {"password": PASSWORD, "password_confirmation": PASSWORD}).status_code, 403)
        page = client.get(self.url)
        response = client.post(self.url, {"password": PASSWORD, "password_confirmation": PASSWORD,
                                         "csrfmiddlewaretoken": page.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.put(self.url).status_code, 405)
