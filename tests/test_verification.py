from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.test import TestCase

from accounts.verification import (
    complete_registration, email_from_verification_token, issue_verification_token,
)


PASSWORD = "A-tide-of-bright-copper-42!"


class VerificationTests(TestCase):
    def test_validation_and_canonical_registration(self):
        with self.assertRaises(ValidationError):
            issue_verification_token("not an email")
        token = issue_verification_token("  Student@BÜCHER.example  ")
        self.assertEqual(email_from_verification_token(token), "student@xn--bcher-kva.example")
        self.assertEqual(get_user_model().objects.count(), 0)
        for password, confirmation in [(PASSWORD, "different"), ("short", "short")]:
            with self.subTest(password=password), self.assertRaises(ValidationError):
                complete_registration(token, password, confirmation)
            self.assertEqual(get_user_model().objects.count(), 0)
        user = complete_registration(token, PASSWORD, PASSWORD)
        self.assertEqual(user.username, "student@xn--bcher-kva.example")
        self.assertEqual(user.email, user.username)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_expiry_is_enforced_on_read_and_completion(self):
        with patch("django.core.signing.time.time", return_value=1000000):
            token = issue_verification_token("student@example.com")
        with patch("django.core.signing.time.time", return_value=1086400):
            self.assertEqual(email_from_verification_token(token), "student@example.com")
            user = complete_registration(token, PASSWORD, PASSWORD)
            user.delete()
        with patch("django.core.signing.time.time", return_value=1086400.01):
            for operation in [lambda: email_from_verification_token(token),
                              lambda: complete_registration(token, PASSWORD, PASSWORD)]:
                with self.assertRaises(signing.SignatureExpired):
                    operation()
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_invalid_tokens_are_rejected_without_writes(self):
        token = issue_verification_token("student@example.com")
        wrong_purpose = signing.dumps("student@example.com", salt="password-reset")
        for invalid in [token + "x", wrong_purpose, "bad", None]:
            with self.subTest(token=repr(invalid)):
                with self.assertRaises(signing.BadSignature):
                    email_from_verification_token(invalid)
                with self.assertRaises(signing.BadSignature):
                    complete_registration(invalid, PASSWORD, PASSWORD)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_replay_preserves_the_existing_account(self):
        token = issue_verification_token("student@example.com")
        user = complete_registration(token, PASSWORD, PASSWORD)
        original_password = user.password
        with self.assertRaises(signing.BadSignature):
            complete_registration(token, PASSWORD + "new", PASSWORD + "new")
        user.refresh_from_db()
        self.assertEqual(user.password, original_password)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_database_failure_rolls_back_consumption(self):
        token = issue_verification_token("student@example.com")
        with patch("accounts.verification.create_verified_user", side_effect=OperationalError("unavailable")):
            with self.assertRaises(OperationalError):
                complete_registration(token, PASSWORD, PASSWORD)
        self.assertEqual(email_from_verification_token(token), "student@example.com")
        self.assertTrue(complete_registration(token, PASSWORD, PASSWORD).check_password(PASSWORD))
