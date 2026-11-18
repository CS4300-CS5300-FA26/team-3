"""Increment 2 uses the existing transaction routes for dialog and fallback forms."""
from datetime import date
from decimal import Decimal
from html import unescape
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from transactions.models import Transaction
from transactions.views import ExpenseForm


DIALOG = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@override_settings(DEBUG=False)
class TransactionDialogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dialog-student")
        self.other = get_user_model().objects.create_user(username="other-student")
        self.client.force_login(self.user)
        self.entry = Transaction.objects.create(
            owner=self.user, kind="expense", amount="40.00", date=date(2026, 10, 15),
            description="Books", category="Books",
        )

    def expense(self, **changes):
        return {"amount": "20.00", "date": "2026-10-15", "description": "Lunch",
                "category": "Food", "is_fixed": "variable", **changes}

    def test_dashboard_descriptions_are_edit_links_with_no_repeated_actions(self):
        response = self.client.get(reverse("dashboard"), {"month": "2026-10"})
        self.assertContains(response, 'data-transaction-row')
        self.assertContains(response, 'data-transaction-dialog')
        self.assertContains(response, f'href="{reverse("edit_transaction", args=[self.entry.pk])}"')
        self.assertNotContains(response, '>Edit</a>')
        self.assertNotContains(response, '>Delete</a>')

    def test_explanation_then_dialog_edit_preserves_month_and_history_on_refresh(self):
        response = self.client.get(reverse("dashboard"), {"month": "2026-10", "period": "all"})
        action = unescape(re.search(r'<form[^>]*action="([^"]*explain[^"]*)"',
                                    response.content.decode()).group(1))
        explained = self.client.post(action, {
            "month": "2026-10", "period": "all", "explain_spending": "1",
        })
        self.assertContains(explained, "Not enough activity yet to summarize")
        updated = self.client.post(reverse("edit_transaction", args=[self.entry.pk]),
                                   self.expense(amount="41.00"), **DIALOG)
        self.assertEqual(updated.status_code, 200)
        refreshed = self.client.get(explained.wsgi_request.get_full_path())
        self.assertEqual(refreshed.context["selected_month"], "2026-10")
        self.assertEqual(refreshed.context["selected_period"], "all")
        self.assertEqual(refreshed.context["expense_total"], Decimal("41.00"))
        self.assertNotContains(refreshed, "Not enough activity yet to summarize")

    def test_create_date_defaults_to_today_and_edit_retains_saved_date(self):
        with patch("transactions.views.timezone.localdate", return_value=date(2026, 11, 16)):
            for route in ("record_income", "record_expense"):
                for options in ({}, DIALOG):
                    response = self.client.get(reverse(route), **options)
                    self.assertEqual(response.context["form"]["date"].value(), date(2026, 11, 16))
        response = self.client.get(reverse("edit_transaction", args=[self.entry.pk]), **DIALOG)
        self.assertEqual(response.context["form"]["date"].value(), self.entry.date)

    def test_dialog_form_reuses_fields_without_page_shell(self):
        response = self.client.get(reverse("record_expense"), **DIALOG)
        self.assertContains(response, "Add expense")
        self.assertContains(response, "Expense Type")
        self.assertContains(response, "Varying Amount")
        self.assertContains(response, "Fixed Amount")
        self.assertNotContains(response, '<html')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertIn("X-Requested-With", response["Vary"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_income_dialog_save_uses_owner_and_reports_success_without_redirect_or_flash(self):
        response = self.client.post(reverse("record_income"), {
            "amount": "123.45", "date": "2026-10-16", "description": "My work",
            "owner": self.other.pk, "kind": "expense",
        }, **DIALOG)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Income saved."})
        entry = Transaction.objects.get(description="My work")
        self.assertEqual(entry.owner, self.user)
        self.assertEqual(entry.kind, "income")
        self.assertFalse(list(self.client.get(reverse("dashboard")).context["messages"]))

    def test_invalid_dialog_retains_values_and_does_not_save(self):
        response = self.client.post(reverse("record_expense"), self.expense(amount="0"), **DIALOG)
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Amount must be greater than zero", status_code=422)
        self.assertContains(response, 'value="Lunch"', status_code=422)
        self.assertEqual(Transaction.objects.filter(owner=self.user).count(), 1)

    def test_recurrence_notice_and_variable_clearing_use_existing_validation(self):
        for frequency in ("daily", "weekly", "monthly"):
            response = self.client.post(reverse("record_expense"), self.expense(
                is_fixed="fixed", recurrence=frequency, next_due_date="2026-11-01", reminder_days="7",
                description=frequency,
            ), **DIALOG)
            self.assertEqual(response.status_code, 200)
            entry = Transaction.objects.get(description=frequency)
            self.assertEqual((entry.recurrence, entry.reminder_days), (frequency, 7))
        response = self.client.post(reverse("edit_transaction", args=[self.entry.pk]), self.expense(
            recurrence="monthly", next_due_date="bad date", reminder_days="100",
        ), **DIALOG)
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.recurrence, "")
        self.assertIsNone(self.entry.next_due_date)

    def test_dialog_payment_still_advances_the_matching_schedule(self):
        self.entry.is_fixed = True
        self.entry.recurrence = "monthly"
        self.entry.next_due_date = date(2026, 10, 17)
        self.entry.save()
        response = self.client.post(reverse("record_expense"), self.expense(
            amount="40.00", description="Books", category="Books", is_fixed="fixed",
        ), **DIALOG)
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.next_due_date, date(2026, 11, 17))

    def test_dialog_edit_preserves_a_concurrent_reminder_delivery_marker(self):
        original_save = ExpenseForm.save
        due = date(2026, 11, 1)

        def record_delivery_before_save(form, *args, **kwargs):
            Transaction.objects.filter(pk=self.entry.pk).update(last_reminded_due_date=due)
            return original_save(form, *args, **kwargs)

        with patch.object(ExpenseForm, "save", record_delivery_before_save):
            response = self.client.post(reverse("edit_transaction", args=[self.entry.pk]),
                                       self.expense(amount="42.00"), **DIALOG)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Transaction updated."})
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.amount, Decimal("42.00"))
        self.assertEqual(self.entry.last_reminded_due_date, due)

    def test_delete_get_is_not_a_mutation_and_post_returns_confirmation(self):
        url = reverse("delete_transaction", args=[self.entry.pk])
        response = self.client.get(url, **DIALOG)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Transaction.objects.filter(pk=self.entry.pk).exists())
        response = self.client.post(url, **DIALOG)
        self.assertEqual(response.json(), {"message": "Transaction deleted."})
        self.assertFalse(Transaction.objects.filter(pk=self.entry.pk).exists())

    def test_dialog_does_not_bypass_csrf_login_or_record_ownership(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(reverse("record_expense"), self.expense(), **DIALOG).status_code, 403)
        self.entry.owner = self.other
        self.entry.save()
        for route in ("edit_transaction", "delete_transaction"):
            url = reverse(route, args=[self.entry.pk])
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(url, self.expense(), **DIALOG).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(reverse("record_expense"), self.expense(), **DIALOG).status_code, 302)
