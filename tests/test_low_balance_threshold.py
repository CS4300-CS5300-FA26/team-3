from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import LowBalanceThreshold
from accounts.views import LowBalanceThresholdForm


class LowBalanceThresholdTests(TestCase):
    def test_account_amount_uses_non_stepping_decimal_input(self):
        student = get_user_model().objects.create_user(username="threshold-scroll-student")
        self.client.force_login(student)

        response = self.client.get(reverse("account_settings"))

        amount_input = response.context["threshold_form"]["amount"].as_widget()
        self.assertIn('type="text"', amount_input)
        self.assertIn('inputmode="decimal"', amount_input)

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

    def test_account_has_empty_threshold_until_set(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        response = self.client.get(reverse("account_settings"))

        self.assertContains(response, "Safety threshold")
        self.assertFalse(response.context["threshold_form"].is_bound)

    def test_account_shows_saved_safety_threshold(self):
        student = get_user_model().objects.create_user(username="student")
        LowBalanceThreshold.objects.create(owner=student, amount=Decimal("150.00"))
        self.client.force_login(student)

        response = self.client.get(reverse("account_settings"))

        self.assertContains(response, "Safety threshold")
        self.assertContains(response, 'value="150.00"')

    def test_student_can_set_threshold_from_account(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)
        dashboard_url = reverse("account_settings")

        self.assertContains(self.client.get(dashboard_url), 'name="amount"')

        response = self.client.post(dashboard_url, {"amount": "150.00"}, follow=True)

        self.assertRedirects(response, dashboard_url)
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00")
        )
        self.assertContains(response, "Safety threshold")
        self.assertContains(response, 'value="150.00"')

    def test_student_can_change_threshold_without_creating_another_row(self):
        student = get_user_model().objects.create_user(username="student")
        LowBalanceThreshold.objects.create(owner=student, amount=Decimal("150.00"))
        self.client.force_login(student)

        response = self.client.post(
            reverse("account_settings"),
            {"amount": "200.00"},
            follow=True,
        )

        self.assertEqual(LowBalanceThreshold.objects.filter(owner=student).count(), 1)
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("200.00")
        )
        self.assertContains(response, 'value="200.00"')

    def test_first_save_handles_another_tab_creating_threshold_after_validation(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)
        dashboard_url = reverse("account_settings")
        original_is_valid = LowBalanceThresholdForm.is_valid

        def validate_after_competing_save(form):
            valid = original_is_valid(form)
            if valid:
                LowBalanceThreshold.objects.create(owner=student, amount=Decimal("90.00"))
            return valid

        with patch.object(LowBalanceThresholdForm, "is_valid", validate_after_competing_save):
            response = self.client.post(dashboard_url, {"amount": "150.00"}, follow=True)

        self.assertRedirects(response, dashboard_url)
        self.assertEqual(LowBalanceThreshold.objects.filter(owner=student).count(), 1)
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00")
        )

    def test_invalid_amount_shows_error_and_does_not_save(self):
        student = get_user_model().objects.create_user(username="student")
        self.client.force_login(student)

        for amount in ("-0.01", "1.001", "not money"):
            with self.subTest(amount=amount):
                response = self.client.post(reverse("account_settings"), {"amount": amount})
                self.assertContains(response, 'class="errorlist"')
                self.assertFalse(LowBalanceThreshold.objects.filter(owner=student).exists())

    def test_post_cannot_set_another_students_threshold(self):
        student = get_user_model().objects.create_user(username="student")
        other = get_user_model().objects.create_user(username="other")
        LowBalanceThreshold.objects.create(owner=other, amount=Decimal("90.00"))
        self.client.force_login(student)

        self.client.post(
            reverse("account_settings"),
            {"amount": "150.00", "owner": other.pk},
        )

        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=student).amount, Decimal("150.00")
        )
        self.assertEqual(
            LowBalanceThreshold.objects.get(owner=other).amount, Decimal("90.00")
        )
