"""D-13 (#25): a fixed expense can repeat monthly with a next due date."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from transactions.models import Transaction
from transactions.views import ExpenseForm

RENT = {
    "amount": "650.00",
    "date": "2026-10-01",
    "description": "Rent",
    "category": "Housing",
    "is_fixed": "fixed",
}
MONTHLY = {"recurrence": "monthly", "next_due_date": "2026-11-01"}


class RecurrenceFormTests(TestCase):
    def test_fixed_expense_accepts_a_monthly_schedule(self):
        form = ExpenseForm({**RENT, **MONTHLY})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["recurrence"], "monthly")
        self.assertEqual(form.cleaned_data["next_due_date"], date(2026, 11, 1))

    def test_fixed_expense_does_not_need_a_schedule(self):
        form = ExpenseForm(RENT)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["recurrence"], "")
        self.assertIsNone(form.cleaned_data["next_due_date"])

    def test_variable_expense_drops_any_schedule_sent_with_it(self):
        form = ExpenseForm({**RENT, "description": "Coffee", "is_fixed": "variable", **MONTHLY})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["recurrence"], "")
        self.assertIsNone(form.cleaned_data["next_due_date"])

    def test_monthly_schedule_needs_a_next_due_date(self):
        form = ExpenseForm({**RENT, "recurrence": "monthly"})

        self.assertFalse(form.is_valid())
        self.assertIn("Choose the next due date.", form.errors["next_due_date"])

    def test_due_date_without_a_schedule_asks_how_often(self):
        form = ExpenseForm({**RENT, "next_due_date": "2026-11-01"})

        self.assertFalse(form.is_valid())
        self.assertIn("Choose how often it repeats.", form.errors["recurrence"])

    def test_unknown_recurrence_and_invalid_date_are_rejected(self):
        for data in (
            {"recurrence": "weekly", "next_due_date": "2026-11-01"},
            {"recurrence": "monthly", "next_due_date": "2026-02-30"},
        ):
            with self.subTest(data=data):
                self.assertFalse(ExpenseForm({**RENT, **data}).is_valid())


class RecurrenceConstraintTests(TestCase):
    """The database refuses schedules the form would never save."""

    def setUp(self):
        self.student = get_user_model().objects.create_user(username="student")

    def create(self, **fields):
        values = {
            "owner": self.student, "kind": Transaction.Kind.EXPENSE, "amount": Decimal("650.00"),
            "date": date(2026, 10, 1), "description": "Rent", "category": "Housing", "is_fixed": True,
        }
        values.update(fields)
        return Transaction.objects.create(**values)

    def test_valid_schedule_is_stored(self):
        rent = self.create(recurrence="monthly", next_due_date=date(2026, 11, 1))

        rent.refresh_from_db()
        self.assertEqual(rent.recurrence, "monthly")
        self.assertEqual(rent.next_due_date, date(2026, 11, 1))

    def test_rejects_schedules_on_variable_expenses_and_income(self):
        for fields in (
            {"is_fixed": False},
            {"kind": Transaction.Kind.INCOME, "category": ""},
        ):
            with self.subTest(fields=fields), transaction.atomic(), self.assertRaises(IntegrityError):
                self.create(recurrence="monthly", next_due_date=date(2026, 11, 1), **fields)

    def test_schedule_and_due_date_come_together(self):
        for fields in ({"recurrence": "monthly"}, {"next_due_date": date(2026, 11, 1)}):
            with self.subTest(fields=fields), transaction.atomic(), self.assertRaises(IntegrityError):
                self.create(**fields)

    def test_rejects_recurrence_values_other_than_monthly(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.create(recurrence="weekly", next_due_date=date(2026, 11, 1))

    def test_insert_without_schedule_columns_is_stored_unscheduled(self):
        # During a deploy the previous code version still serves requests, and a
        # rollback runs it against the migrated schema. Its inserts omit the new
        # columns, so the database itself must supply an empty recurrence.
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {Transaction._meta.db_table} "
                "(owner_id, kind, amount, date, description, category, is_fixed, is_demo, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [self.student.pk, "income", Decimal("80.00"), date(2026, 10, 1), "Old code",
                 "", False, False, timezone.now()],
            )

        stored = Transaction.objects.get(description="Old code")
        self.assertEqual(stored.recurrence, "")
        self.assertIsNone(stored.next_due_date)


class RecurrenceViewTests(TestCase):
    def setUp(self):
        self.student = get_user_model().objects.create_user(username="student")
        self.client.force_login(self.student)

    def test_saving_a_monthly_fixed_expense_stores_the_schedule(self):
        response = self.client.post(reverse("record_expense"), {**RENT, **MONTHLY})

        self.assertRedirects(response, reverse("record_expense"))
        rent = Transaction.objects.get(owner=self.student, description="Rent")
        self.assertEqual(rent.recurrence, "monthly")
        self.assertEqual(rent.next_due_date, date(2026, 11, 1))

    def test_schedule_fields_hide_for_variable_and_stay_open_for_fixed_with_errors(self):
        # Before a type is chosen the server leaves the schedule usable, so it
        # works without JavaScript; the page script hides it until Fixed is chosen.
        page = self.client.get(reverse("record_expense")).content.decode()
        self.assertIn('id="recurrence-fields"', page)
        self.assertNotIn('id="recurrence-fields" hidden', page)

        variable = self.client.post(reverse("record_expense"), {**RENT, "is_fixed": "variable", "amount": ""})
        self.assertContains(variable, 'id="recurrence-fields" hidden disabled')

        response = self.client.post(reverse("record_expense"), {**RENT, "recurrence": "monthly"})

        self.assertContains(response, "Choose the next due date.")
        self.assertContains(response, 'id="recurrence-fields"')
        self.assertNotContains(response, 'id="recurrence-fields" hidden')
        self.assertFalse(Transaction.objects.filter(owner=self.student).exists())

    def test_variable_expense_saves_despite_stale_or_malformed_schedule_values(self):
        # A hidden schedule must never block saving: its values are ignored
        # before they are validated.
        for schedule in (
            {"recurrence": "monthly", "next_due_date": "2026-02-30"},
            {"recurrence": "weekly", "next_due_date": "not a date"},
        ):
            with self.subTest(schedule=schedule):
                response = self.client.post(
                    reverse("record_expense"),
                    {**RENT, "description": "Coffee", "is_fixed": "variable", **schedule},
                )

                self.assertRedirects(response, reverse("record_expense"))
                coffee = Transaction.objects.filter(owner=self.student, description="Coffee").latest("id")
                self.assertEqual(coffee.recurrence, "")
                self.assertIsNone(coffee.next_due_date)

    def test_changing_to_variable_saves_despite_malformed_schedule_values(self):
        self.client.post(reverse("record_expense"), {**RENT, **MONTHLY})
        rent = Transaction.objects.get(owner=self.student, description="Rent")

        response = self.client.post(
            reverse("edit_transaction", args=[rent.pk]),
            {**RENT, "is_fixed": "variable", "recurrence": "monthly", "next_due_date": "2026-02-30"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        rent.refresh_from_db()
        self.assertFalse(rent.is_fixed)
        self.assertEqual(rent.recurrence, "")
        self.assertIsNone(rent.next_due_date)

    def test_fixed_expense_still_validates_its_schedule(self):
        response = self.client.post(
            reverse("record_expense"), {**RENT, "recurrence": "monthly", "next_due_date": "2026-02-30"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date.")
        self.assertNotContains(response, 'id="recurrence-fields" hidden')
        self.assertFalse(Transaction.objects.filter(owner=self.student).exists())

    def test_hidden_schedule_controls_are_disabled(self):
        response = self.client.post(reverse("record_expense"), {**RENT, "is_fixed": "variable", "amount": ""})

        self.assertContains(response, 'id="recurrence-fields" hidden disabled')

    def test_dashboard_shows_the_next_due_date(self):
        self.client.post(reverse("record_expense"), {**RENT, **MONTHLY})
        self.client.post(reverse("record_expense"), {**RENT, "description": "Groceries", "category": "Food"})

        response = self.client.get(reverse("dashboard"), {"month": "2026-10"})

        self.assertContains(response, "Monthly, next due Nov 1, 2026", count=1)

    def test_editing_a_fixed_expense_to_variable_clears_its_schedule(self):
        self.client.post(reverse("record_expense"), {**RENT, **MONTHLY})
        rent = Transaction.objects.get(owner=self.student, description="Rent")
        edit_url = reverse("edit_transaction", args=[rent.pk])

        edit_page = self.client.get(edit_url)
        self.assertContains(edit_page, 'value="2026-11-01"')
        self.assertNotContains(edit_page, 'id="recurrence-fields" hidden')

        self.client.post(edit_url, {**RENT, "is_fixed": "variable", **MONTHLY})

        rent.refresh_from_db()
        self.assertFalse(rent.is_fixed)
        self.assertEqual(rent.recurrence, "")
        self.assertIsNone(rent.next_due_date)

    def test_income_ignores_schedule_fields(self):
        self.client.post(reverse("record_income"), {
            "amount": "1200.00", "date": "2026-10-01", "description": "Paycheck", **MONTHLY,
        })

        paycheck = Transaction.objects.get(owner=self.student, description="Paycheck")
        self.assertEqual(paycheck.recurrence, "")
        self.assertIsNone(paycheck.next_due_date)
