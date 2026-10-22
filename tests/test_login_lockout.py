from datetime import timedelta
from unittest.mock import patch
from accounts.lockout import cleanup_stale_attempts
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, connections, close_old_connections
from django.test import Client, TransactionTestCase
from unittest import skipUnless
from accounts.models import FailedSignIn, LoginAttempt
from transactions.models import Transaction


class LoginLockoutTests(TestCase):

    def create_user(self, email):
        return get_user_model().objects.create_user(
            username=email,
            email=email,
            password="TestPassword123!",
        )

    def fail_login(self, email):
        return self.client.post(
            reverse("sign_in"),
            {
                "email": email,
                "password": "WrongPassword123",
            },
        )

    def test_lockout_after_five_failures(self):
        # Create a test user
        self.create_user("test@example.com")

        # Submit five incorrect passwords
        for _ in range(5):
            response = self.fail_login("test@example.com")
            self.assertContains(
                response,
                "Email or password is incorrect",
            )

        # Confirm the email is blocked
        attempt = LoginAttempt.objects.get(email="test@example.com")
        self.assertEqual(attempt.failed_count, 5)
        self.assertGreater(attempt.blocked_until, timezone.now())

        # Confirm a correct password cannot bypass the lockout
        with patch("accounts.lockout.authenticate") as authenticate:
            response = self.client.post(
                reverse("sign_in"),
                {
                    "email": "test@example.com",
                    "password": "TestPassword123!",
                },
            )
            authenticate.assert_not_called()

        self.assertContains(
            response,
            "Too many attempts. Try again in 15 minutes.",
        )

    def test_lockout_expires(self):
        # Create a test user
        self.create_user("test@example.com")

        # Trigger the lockout
        for _ in range(5):
            self.fail_login("test@example.com")

        # Move the lockout expiration into the past
        attempt = LoginAttempt.objects.get(email="test@example.com")
        attempt.blocked_until = timezone.now() - timedelta(seconds=1)
        attempt.save()

        # Sign in with the correct password
        response = self.client.post(
            reverse("sign_in"),
            {
                "email": "test@example.com",
                "password": "TestPassword123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))

        # Confirm the lockout is no longer active
        attempt = LoginAttempt.objects.filter(
            email="test@example.com"
        ).first()

        if attempt is not None:
            self.assertFalse(
                attempt.blocked_until
                and attempt.blocked_until > timezone.now()
            )
            self.assertEqual(attempt.failed_count, 0)

        self.assertFalse(
            FailedSignIn.objects.filter(
                email="test@example.com"
            ).exists()
        )

    def test_lockout_is_separate_for_each_email(self):
        # Create two test users
        self.create_user("user1@example.com")
        self.create_user("user2@example.com")

        # Block the first user
        for _ in range(5):
            self.fail_login("user1@example.com")

        response = self.client.post(
            reverse("sign_in"),
            {
                "email": "user1@example.com",
                "password": "TestPassword123!",
            },
        )

        self.assertContains(
            response,
            "Too many attempts. Try again in 15 minutes.",
        )

        # Confirm the second user can still sign in
        response = self.client.post(
            reverse("sign_in"),
            {
                "email": "user2@example.com",
                "password": "TestPassword123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_rolling_fifteen_minute_window(self):
        # Create a test user
        self.create_user("test@example.com")

        # Record four failed sign ins
        for _ in range(4):
            self.fail_login("test@example.com")

        # Move those failures outside the 15 minute window
        old_time = timezone.now() - timedelta(minutes=16)

        FailedSignIn.objects.filter(
            email="test@example.com"
        ).update(created_at=old_time)

        # Submit one new failed sign in
        self.fail_login("test@example.com")

        # Only the recent failure should count
        attempt = LoginAttempt.objects.get(
            email="test@example.com"
        )

        self.assertEqual(attempt.failed_count, 1)
        self.assertFalse(
            attempt.blocked_until
            and attempt.blocked_until > timezone.now()
        )

    def test_dashboard_requires_login(self):
        # Try opening the dashboard without signing in
        response = self.client.get(reverse("dashboard"))

        # Confirm the user is redirected to sign in
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(reverse("sign_in"))
        )

    def test_dashboard_only_shows_own_transactions(self):
        # Create two users
        user1 = self.create_user("user1@example.com")
        user2 = self.create_user("user2@example.com")

        # Create transactions for each user
        Transaction.objects.create(
            owner=user1,
            kind="expense",
            amount="25.00",
            date="2026-10-22",
            description="User 1 Purchase",
            category="Food",
        )

        Transaction.objects.create(
            owner=user2,
            kind="expense",
            amount="50.00",
            date="2026-10-22",
            description="User 2 Purchase",
            category="Shopping",
        )

        # Sign in as the first user
        self.client.force_login(user1)

        response = self.client.get(reverse("dashboard"),{"month": "2026-10"},)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User 1 Purchase")
        self.assertNotContains(response, "User 2 Purchase")

    def test_logout_invalidates_session(self):
        # Create and sign in a user
        user = self.create_user("test@example.com")
        self.client.force_login(user)

        # Confirm the dashboard is accessible
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

        # Sign out using POST
        response = self.client.post(reverse("sign_out"))
        self.assertRedirects(response, reverse("sign_in"))

        # Confirm the authenticated session is gone
        self.assertNotIn("_auth_user_id", self.client.session)

        # Confirm the dashboard is protected again
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(reverse("sign_in"))
        )


    def test_cleanup_removes_stale_failures(self):
        # Create an old inactive login record
        LoginAttempt.objects.create(
            email="old@example.com",
            failed_count=2,
            first_failed_at=timezone.now() - timedelta(minutes=30),
        )

        FailedSignIn.objects.create(
            email="old@example.com",
            created_at=timezone.now() - timedelta(minutes=30),
        )

        cleanup_stale_attempts()

        # Keep the parent record to avoid racing with sign-in
        self.assertTrue(
            LoginAttempt.objects.filter(
                email="old@example.com"
            ).exists()
        )

        self.assertFalse(
            FailedSignIn.objects.filter(
                email="old@example.com"
            ).exists()
        )

    def test_cleanup_preserves_active_lockouts(self):
        # Create an active lockout with old failures
        LoginAttempt.objects.create(
            email="blocked@example.com",
            failed_count=5,
            first_failed_at=timezone.now() - timedelta(minutes=20),
            blocked_until=timezone.now() + timedelta(minutes=10),
        )

        cleanup_stale_attempts()

        # The active lockout must remain
        attempt = LoginAttempt.objects.get(
            email="blocked@example.com"
        )

        self.assertGreater(
            attempt.blocked_until,
            timezone.now()
        )



@skipUnless(
    connection.vendor == "postgresql",
    "Concurrency test requires PostgreSQL",
)
class PostgreSQLLoginConcurrencyTests(TransactionTestCase):

    def test_simultaneous_failed_logins_trigger_lockout(self):
        email = "concurrent@example.com"

        # Create a student account
        get_user_model().objects.create_user(
            username=email,
            email=email,
            password="TestPassword123!",
        )

        # Start five requests at approximately the same time
        barrier = Barrier(5)

        def attempt_login():
            close_old_connections()

            try:
                client = Client()
                barrier.wait(timeout=10)

                return client.post(
                    reverse("sign_in"),
                    {
                        "email": email,
                        "password": "WrongPassword123",
                    },
                ).status_code
            finally:
                connections.close_all()

        # Run each request with its own database connection
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(
                executor.map(
                    lambda _: attempt_login(),
                    range(5),
                )
            )

        # All five requests should finish successfully
        self.assertEqual(results, [200] * 5)

        # All failures must be recorded
        attempt = LoginAttempt.objects.get(email=email)

        self.assertEqual(attempt.failed_count, 5)
        self.assertEqual(
            FailedSignIn.objects.filter(email=email).count(),
            5,
        )
        self.assertGreater(attempt.blocked_until, timezone.now())

        # A correct password must not bypass the lockout
        with patch("accounts.lockout.authenticate") as authenticate:
            response = self.client.post(
                reverse("sign_in"),
                {
                    "email": email,
                    "password": "TestPassword123!",
                },
            )
            authenticate.assert_not_called()

        self.assertContains(
            response,
            "Too many attempts. Try again in 15 minutes.",
        )
