from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.identity import create_verified_user, normalize_email


PASSWORD = "A-tide-of-bright-copper-42!"


class EmailIdentityTests(TestCase):
    def test_normalization_is_idempotent_and_does_not_create_users(self):
        canonical = normalize_email("  Student+Budget@Example.COM  ")
        self.assertEqual(canonical, "student+budget@example.com")
        self.assertEqual(normalize_email(canonical), canonical)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_supported_punctuation_and_plus_tags_are_preserved(self):
        self.assertEqual(normalize_email("O'Neil+Budget@Example.com"),
                         "o'neil+budget@example.com")
        self.assertNotEqual(normalize_email("student+budget@example.com"),
                            normalize_email("student@example.com"))
        self.assertNotEqual(normalize_email("first.last@example.com"),
                            normalize_email("firstlast@example.com"))

    def test_length_limit_applies_to_canonical_email(self):
        # Each label/local part is valid; only total length crosses the limit.
        email = "a" * 64 + "@" + "b" * 63 + "." + "c" * 17 + ".com"
        self.assertEqual(len(email), 150)
        self.assertEqual(normalize_email("  " + email + "  "), email)
        with self.assertRaises(ValidationError):
            normalize_email(email.replace("c" * 17, "c" * 18))

    def test_lowercase_expansion_is_counted_in_canonical_length(self):
        email = "a" * 64 + "@" + "b" * 63 + "." + "c" * 16 + "İ.com"
        self.assertEqual(len(email), 150)
        with self.assertRaises(ValidationError):
            normalize_email(email)

    def test_invalid_email_inputs_fail_without_writes(self):
        invalid = [None, 123, [], {}, b"student@example.com", "", "  ",
                   "student", "student@", "@example.com", "a b@example.com",
                   "a@example..com", "a\n@example.com", "a@example.com\r\n",
                   "\tstudent@example.com", "a\0@example.com", "a\u200b@example.com",
                   "a\u202e@example.com", "a\ud800@example.com"]
        for email in invalid:
            with self.subTest(email=repr(email)), self.assertRaises(ValidationError):
                normalize_email(email)
        self.assertEqual(get_user_model().objects.count(), 0)


class VerifiedUserTests(TestCase):
    def test_canonical_email_at_length_limit_can_be_saved(self):
        email = "a" * 64 + "@" + "b" * 63 + "." + "c" * 17 + ".com"
        user = create_verified_user(email, PASSWORD)
        user.refresh_from_db()
        self.assertEqual(user.username, email)
        self.assertEqual(user.email, email)

    def test_verified_identity_creates_one_ordinary_active_user(self):
        user = create_verified_user("  O'Neil+Budget@Example.COM  ", PASSWORD)
        user.refresh_from_db()
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(user.username, "o'neil+budget@example.com")
        self.assertEqual(user.email, user.username)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(authenticate(username=user.username, password=PASSWORD), user)

    def test_password_is_preserved_exactly(self):
        password = "  Bright-Copper-Tide-42!  "
        user = create_verified_user("student@example.com", password)
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.check_password(password.strip()))
        self.assertFalse(user.check_password(password.lower()))

    def test_configured_password_failures_create_no_users(self):
        for password in ["Ab3!xyZ", "password", "123456789", "student@example.com"]:
            with self.subTest(password=password), self.assertRaises(ValidationError):
                create_verified_user("student@example.com", password)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_missing_or_non_string_passwords_create_no_users(self):
        for password in [None, "", 12345678, [], {}, b"some-password"]:
            with self.subTest(password=repr(password)), self.assertRaises(ValidationError):
                create_verified_user("student@example.com", password)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_invalid_identity_is_rejected_before_creation(self):
        with self.assertRaises(ValidationError):
            create_verified_user("not an email", PASSWORD)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_duplicates_preserve_original_account_and_outer_transaction(self):
        user = create_verified_user("student@example.com", PASSWORD)
        original_password = user.password
        for email in ["student@example.com", "  STUDENT@EXAMPLE.COM  "]:
            with self.subTest(email=email), transaction.atomic():
                with self.assertRaises(IntegrityError):
                    create_verified_user(email, "A-different-copper-tide-71!")
                user.refresh_from_db()
                self.assertEqual(get_user_model().objects.count(), 1)
                self.assertEqual(user.password, original_password)
                self.assertEqual(user.email, "student@example.com")
                self.assertTrue(user.is_active)
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                # A write as well as a read must work after the handled duplicate.
                other = create_verified_user("another@example.com", PASSWORD)
                other.delete()

    def test_database_itself_refuses_duplicate_username(self):
        create_verified_user("student@example.com", PASSWORD)
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create(username="student@example.com")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_plus_and_base_addresses_create_distinct_accounts(self):
        base = create_verified_user("student@example.com", PASSWORD)
        tagged = create_verified_user("student+budget@example.com", PASSWORD)
        self.assertNotEqual(base.pk, tagged.pk)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_unicode_domain_round_trips_without_nfkc_conversion(self):
        # NFKC maps the fullwidth e to ASCII; the identity contract preserves it.
        email = "student@ｅxample.com"
        user = create_verified_user(email, PASSWORD)
        user.refresh_from_db()
        self.assertEqual(user.username, email)
        self.assertEqual(user.email, email)
        self.assertEqual(authenticate(username=normalize_email(email), password=PASSWORD), user)
        self.assertNotEqual(normalize_email(email), normalize_email("student@example.com"))

    def test_existing_non_email_username_still_authenticates(self):
        existing = get_user_model().objects.create_user(username="existing-admin", password=PASSWORD)
        create_verified_user("student@example.com", PASSWORD)
        self.assertEqual(authenticate(username="existing-admin", password=PASSWORD), existing)
