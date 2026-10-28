from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import LowBalanceThreshold


class LowBalanceThresholdTests(TestCase):
    def test_student_has_no_threshold_until_one_is_set(self):
        student = get_user_model().objects.create_user(username="student")

        self.assertFalse(LowBalanceThreshold.objects.filter(owner=student).exists())

    def test_threshold_is_saved_for_one_student_only(self):
        student = get_user_model().objects.create_user(username="student")
        other = get_user_model().objects.create_user(username="other")

        LowBalanceThreshold.objects.create(owner=student, amount=Decimal("150.00"))

        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00")
        )
        self.assertFalse(LowBalanceThreshold.objects.filter(owner=other).exists())

    def test_student_cannot_have_two_threshold_rows(self):
        student = get_user_model().objects.create_user(username="student")
        LowBalanceThreshold.objects.create(owner=student, amount=Decimal("150.00"))

        with transaction.atomic(), self.assertRaises(IntegrityError):
            LowBalanceThreshold.objects.create(owner=student, amount=Decimal("200.00"))

        self.assertEqual(LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00"))

    def test_negative_amount_is_rejected(self):
        student = get_user_model().objects.create_user(username="student")
        threshold = LowBalanceThreshold(owner=student, amount=Decimal("-0.01"))

        with self.assertRaises(ValidationError):
            threshold.full_clean()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            threshold.save()

    def test_zero_is_allowed_and_fractional_cents_are_rejected(self):
        student = get_user_model().objects.create_user(username="student")
        LowBalanceThreshold(owner=student, amount=Decimal("0.00")).full_clean()

        with self.assertRaises(ValidationError):
            LowBalanceThreshold(owner=student, amount=Decimal("1.001")).full_clean()

    def test_dashboard_says_when_safety_threshold_is_not_set(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Safety threshold")
        self.assertContains(response, "Not set")

    def test_dashboard_shows_saved_safety_threshold(self):
        student = get_user_model().objects.create_user(username="student")
        LowBalanceThreshold.objects.create(owner=student, amount=Decimal("150.00"))
        self.client.force_login(student)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Safety threshold")
        self.assertContains(response, "$150.00")

    def test_threshold_editor_stays_collapsed_until_requested_or_invalid(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, '<details class="threshold-setting">')
        self.assertContains(response, '<summary class="threshold-summary">Safety threshold:')
        self.assertContains(response, "Not set")

        response = self.client.post(reverse("dashboard"), {"amount": "-0.01"})
        self.assertContains(response, '<details class="threshold-setting" open>')
        self.assertContains(response, 'class="errorlist"')

    def test_student_can_set_threshold_from_dashboard(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)
        dashboard_url = reverse("dashboard") + "?month=2026-10"

        self.assertContains(self.client.get(dashboard_url), 'name="amount"')

        response = self.client.post(dashboard_url, {"amount": "150.00"}, follow=True)

        self.assertRedirects(response, dashboard_url)
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00")
        )
        self.assertContains(response, "Safety threshold")
        self.assertContains(response, "$150.00")

    def test_student_can_change_threshold_without_creating_another_row(self):
        student = get_user_model().objects.create_user(username="student")
        LowBalanceThreshold.objects.create(owner=student, amount=Decimal("150.00"))
        self.client.force_login(student)

        response = self.client.post(
            reverse("dashboard") + "?month=2026-10",
            {"amount": "200.00"},
            follow=True,
        )

        self.assertEqual(LowBalanceThreshold.objects.filter(owner=student).count(), 1)
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("200.00")
        )
        self.assertContains(response, "$200.00")

    def test_invalid_amount_shows_error_and_does_not_save(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        for amount in ("-0.01", "1.001", "not money"):
            with self.subTest(amount=amount):
                response = self.client.post(reverse("dashboard"), {"amount": amount})
                self.assertContains(response, 'class="errorlist"')
                self.assertFalse(LowBalanceThreshold.objects.filter(owner=student).exists())

    def test_post_cannot_set_another_students_threshold(self):
        student = get_user_model().objects.create_user(username="student")
        other = get_user_model().objects.create_user(username="other")
        LowBalanceThreshold.objects.create(owner=other, amount=Decimal("90.00"))
        self.client.force_login(student)

        self.client.post(
            reverse("dashboard"),
            {"amount": "150.00", "owner": other.pk},
        )

        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00")
        )
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=other).amount, Decimal("90.00")
        )
