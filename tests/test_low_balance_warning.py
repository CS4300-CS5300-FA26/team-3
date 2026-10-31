from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import LowBalanceThreshold
from transactions.models import Transaction


class LowBalanceWarningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = get_user_model().objects.create_user(username="warning-student")
        LowBalanceThreshold.objects.create(owner=cls.student, amount=Decimal("150.00"))
        Transaction.objects.create(
            owner=cls.student,
            kind=Transaction.Kind.INCOME,
            amount=Decimal("310.00"),
            date=date(2026, 10, 1),
            description="October income",
        )

    def setUp(self):
        self.client.force_login(self.student)

    def dashboard(self):
        return self.client.get(reverse("dashboard"), {"month": "2026-10"})

    def test_warning_shown_below_threshold(self):
        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("190.00"),
            date=date(2026, 10, 2),
            description="October expense",
            category="Food",
        )

        response = self.dashboard()

        self.assertEqual(response.context["remaining_budget"], Decimal("120.00"))
        self.assertContains(response, "You are below your $150.00 safety threshold")

    def test_no_warning_above_threshold(self):
        response = self.dashboard()

        self.assertEqual(response.context["remaining_budget"], Decimal("310.00"))
        self.assertNotContains(response, "You are below your $150.00 safety threshold")

    def test_no_warning_at_threshold(self):
        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("160.00"),
            date=date(2026, 10, 2),
            description="October expense",
            category="Food",
        )

        response = self.dashboard()

        self.assertEqual(response.context["remaining_budget"], Decimal("150.00"))
        self.assertNotContains(response, "You are below your $150.00 safety threshold")

    def test_no_warning_without_a_saved_threshold(self):
        LowBalanceThreshold.objects.filter(owner=self.student).delete()
        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("190.00"),
            date=date(2026, 10, 2),
            description="October expense",
            category="Food",
        )

        response = self.dashboard()

        self.assertEqual(response.context["remaining_budget"], Decimal("120.00"))
        self.assertNotContains(response, "You are below your $150.00 safety threshold")
