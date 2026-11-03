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

    def dashboard(self, month="2026-10"):
        return self.client.get(reverse("dashboard"), {"month": month})

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
        self.assertNotContains(response, "You are below your")

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
        self.assertNotContains(response, "You are below your")

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
        self.assertNotContains(response, "You are below your")

    def test_warning_follows_the_selected_month(self):
        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.INCOME,
            amount=Decimal("310.00"),
            date=date(2026, 9, 1),
            description="September income",
        )
        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("190.00"),
            date=date(2026, 10, 2),
            description="October expense",
            category="Food",
        )

        october = self.dashboard("2026-10")
        september = self.dashboard("2026-09")

        self.assertEqual(october.context["remaining_budget"], Decimal("120.00"))
        self.assertContains(october, "You are below your $150.00 safety threshold")
        self.assertEqual(september.context["selected_month"], "2026-09")
        self.assertEqual(september.context["remaining_budget"], Decimal("310.00"))
        self.assertNotContains(september, "You are below your")

    def test_warning_uses_only_the_signed_in_students_data(self):
        other = get_user_model().objects.create_user(username="other-warning-student")
        LowBalanceThreshold.objects.create(owner=other, amount=Decimal("500.00"))
        Transaction.objects.create(
            owner=other,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("300.00"),
            date=date(2026, 10, 2),
            description="Other student's expense",
            category="Food",
        )

        above = self.dashboard()
        self.assertEqual(above.context["remaining_budget"], Decimal("310.00"))
        self.assertNotContains(above, "You are below your")

        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("190.00"),
            date=date(2026, 10, 2),
            description="October expense",
            category="Food",
        )
        Transaction.objects.create(
            owner=other,
            kind=Transaction.Kind.INCOME,
            amount=Decimal("800.00"),
            date=date(2026, 10, 3),
            description="Other student's income",
        )

        below = self.dashboard()
        self.assertEqual(below.context["remaining_budget"], Decimal("120.00"))
        self.assertContains(below, "You are below your $150.00 safety threshold")

    def test_warning_reflects_a_saved_threshold_change(self):
        Transaction.objects.create(
            owner=self.student,
            kind=Transaction.Kind.EXPENSE,
            amount=Decimal("190.00"),
            date=date(2026, 10, 2),
            description="October expense",
            category="Food",
        )
        dashboard_url = reverse("dashboard") + "?month=2026-10"

        self.assertContains(self.dashboard(), "You are below your $150.00 safety threshold")

        lower = self.client.post(dashboard_url, {"amount": "100.00"}, follow=True)
        self.assertRedirects(lower, dashboard_url)
        self.assertEqual(lower.context["remaining_budget"], Decimal("120.00"))
        self.assertNotContains(lower, "You are below your")

        higher = self.client.post(dashboard_url, {"amount": "200.00"}, follow=True)
        self.assertRedirects(higher, dashboard_url)
        self.assertEqual(higher.context["remaining_budget"], Decimal("120.00"))
        self.assertContains(higher, "You are below your $200.00 safety threshold")
