"""Monthly details and explicit explanations (#74, #9)."""
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import SpendingSummaryBudget
from django.urls import reverse

from accounts.spending_summary import SpendingSummaryError, claim_summary_request, generate_spending_summary
from transactions.models import Transaction


class MonthlyDetailsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="details")
        self.client.force_login(self.user)
        for index in range(9):
            Transaction.objects.create(owner=self.user, kind="income", amount="1.00",
                                       date="2026-11-01", description=f"Private income {index}")
        Transaction.objects.create(owner=self.user, kind="expense", amount="0.30", category="Food & drink",
                                   date="2026-11-03", description="Private expense")

    def explain(self, **extra):
        return self.client.post(reverse("explain_spending"), {"month": "2026-11", "explain_spending": "1", **extra})

    def test_details_fragment_and_fallback_share_exact_monthly_data(self):
        url = reverse("spending_by_category") + "?month=2026-11&period=all&category=Missing"
        page = self.client.get(url)
        fragment = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertNotContains(fragment, "<!DOCTYPE")
        for response in [page, fragment]:
            self.assertContains(response, "Spending details")
            self.assertContains(response, "$0.30")
            self.assertContains(response, "100.00%")
            self.assertContains(response, "category=Food%20%26%20drink")
            self.assertEqual(response.context["expense_count"], 1)
        self.assertIn("X-Requested-With", fragment.headers["Vary"])
        self.assertIn("no-store", fragment.headers["Cache-Control"])

    @patch("accounts.spending_summary.urlopen")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_ten_transactions_not_ten_expenses_and_history_is_irrelevant(self, provider):
        import json
        provider.return_value = io.BytesIO(json.dumps({"output_text": json.dumps(["Food & drink totaled $0.30."])}).encode())
        response = self.explain(period="last_3_days", category="Missing", kind="income")
        self.assertContains(response, "Food &amp; drink totaled $0.30.")
        provider.assert_called_once()
        payload = provider.call_args.args[0].data.decode()
        self.assertNotIn("Private", payload)
        self.assertIn("0.30", payload)

    @patch("accounts.spending_summary.urlopen")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_rejected_observations_have_failure_and_retry(self, provider):
        provider.return_value = io.BytesIO(b'{"output_text": "[]"}')
        response = self.explain()
        self.assertContains(response, "Unable to generate spending summary right now.")
        self.assertContains(response, "Try again")

    @patch("accounts.spending_summary.urlopen")
    def test_income_only_skips_provider(self, provider):
        Transaction.objects.filter(kind="expense").update(kind="income", category="")
        self.assertContains(self.explain(), "No expenses to summarize for this month.")
        provider.assert_not_called()

    @patch("accounts.spending_summary.urlopen")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_repeated_requests_are_bounded_even_after_provider_failure(self, provider):
        provider.side_effect = OSError("offline")
        for _ in range(5):
            self.explain()
        limited = self.explain()
        self.assertContains(limited, "Too many summary requests")
        self.assertNotContains(limited, 'class="explanation-form"')
        self.assertEqual(provider.call_count, 5)

    def test_ready_explanation_has_no_visible_empty_status_panel(self):
        response = self.client.get(reverse("spending_by_category"), {"month": "2026-11"})
        self.assertContains(response, 'class="summary-result" role="status" tabindex="-1" hidden')
        self.assertContains(response, "Explain my spending")

    @patch("accounts.spending_summary.urlopen")
    def test_dashboard_offers_one_post_action_and_get_does_not_generate(self, provider):
        response = self.client.get(reverse("dashboard"), {"month": "2026-11"})
        self.assertContains(response, ">Explain my spending</button>", count=1)
        self.assertContains(response, 'data-spending-details method="post"')
        self.assertNotContains(response, "View details")
        self.assertContains(response, "data-spending-details")
        self.client.get(reverse("spending_by_category"), {"month": "2026-11"})
        provider.assert_not_called()

    @patch("transactions.views.generate_spending_summary")
    def test_expired_session_redirects_without_generating_or_spending_admission(self, provider):
        self.client.logout()
        response = self.client.post(reverse("explain_spending"), {"month": "2026-11"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertRedirects(response, reverse("sign_in") + "?next=" + reverse("explain_spending"))
        provider.assert_not_called()
        self.assertFalse(SpendingSummaryBudget.objects.exists())

    @patch("accounts.spending_summary.urlopen", return_value=io.BytesIO(b"\xff"))
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_invalid_utf8_is_a_safe_service_failure(self, provider):
        with self.assertRaises(SpendingSummaryError):
            generate_spending_summary([{"category": "Food", "total": Decimal("0.30"), "count": 1}])


class SummaryAdmissionTests(TestCase):
    def test_global_cap_is_bounded_and_window_expires(self):
        now = timezone.now()
        with patch("accounts.spending_summary.timezone.now", return_value=now):
            for user in range(100):
                self.assertTrue(claim_summary_request(user))
            self.assertFalse(claim_summary_request(101))
            self.assertEqual(len(SpendingSummaryBudget.objects.get().admitted_at), 100)
        with patch("accounts.spending_summary.timezone.now", return_value=now + timedelta(hours=1)):
            self.assertTrue(claim_summary_request(101))
        self.assertEqual(len(SpendingSummaryBudget.objects.get().admitted_at), 1)


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL")
class SummaryAdmissionConcurrencyTests(TransactionTestCase):
    def test_competing_workers_admit_only_remaining_user_slot(self):
        for _ in range(4):
            self.assertTrue(claim_summary_request(7))
        barrier = Barrier(4)

        def claim(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return claim_summary_request(7)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=4) as workers:
            admitted = list(workers.map(claim, range(4)))
        self.assertEqual(admitted.count(True), 1)
        self.assertEqual(len(SpendingSummaryBudget.objects.get().admitted_at), 5)
