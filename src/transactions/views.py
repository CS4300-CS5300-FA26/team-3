from datetime import date
import unicodedata

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Transaction


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["amount", "date", "description"]
        labels = {"amount": "Amount ($)", "description": "Source"}
        widgets = {
            "amount": forms.TextInput(attrs={"inputmode": "decimal"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        error_messages = {
            "amount": {"min_value": "Amount must be greater than zero"},
            "description": {"required": "Enter an income source."},
        }


EXPENSE_CATEGORIES = ["Housing", "Food", "Books", "Transportation", "Other"]
INVISIBLE_CATEGORIES = {"Cc", "Cf", "Mn", "Me"}
# Characters outside those categories that still draw as empty space: the blank
# Braille pattern and the Hangul fillers.
BLANK_CHARACTERS = {"⠀", "ᅟ", "ᅠ", "ㅤ", "ﾠ"}


class ExpenseForm(forms.ModelForm):
    # The allowed list lives in the form, not on the model field, so changing it
    # needs no migration. The model's check constraint still rejects blank categories.
    category = forms.ChoiceField(
        choices=[("", "Select a category")] + [(c, c) for c in EXPENSE_CATEGORIES],
        error_messages={"required": "Choose a category"},
    )
    is_fixed = forms.TypedChoiceField(
        label="Type",
        choices=[("fixed", "Fixed"), ("variable", "Variable")],
        coerce=lambda value: value == "fixed",
        widget=forms.RadioSelect,
        error_messages={"required": "Choose fixed or variable"},
    )
    recurrence = forms.ChoiceField(
        label="Repeats",
        choices=Transaction.Recurrence.choices,
        required=False,
    )

    class Meta:
        model = Transaction
        fields = ["amount", "date", "description", "category", "is_fixed", "recurrence", "next_due_date"]
        labels = {"amount": "Amount ($)", "description": "Description", "next_due_date": "Next due date"}
        widgets = {
            "amount": forms.TextInput(attrs={"inputmode": "decimal"}),
            "date": forms.DateInput(attrs={"type": "date"}),
            "next_due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        error_messages = {
            "amount": {"min_value": "Amount must be greater than zero"},
            "description": {"required": "Enter an expense description."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A variable expense's schedule is hidden on the page, so its values must
        # never block saving. Blank them before field validation runs; clean()
        # still clears the schedule for any type other than Fixed.
        if self.is_bound and self.data.get(self.add_prefix("is_fixed")) == "variable":
            self.data = self.data.copy()
            for name in ("recurrence", "next_due_date"):
                self.data[self.add_prefix(name)] = ""

    def clean_description(self):
        description = self.cleaned_data["description"]
        # These pass Django's whitespace strip but display as nothing on their own:
        # control (Cc) and format (Cf) characters such as a zero-width space,
        # combining marks (Mn, Me) with no letter to attach to, and the blank
        # characters above. Reject a description made only of them; inside visible
        # text they are kept as typed.
        if all(
            char.isspace()
            or char in BLANK_CHARACTERS
            or unicodedata.category(char) in INVISIBLE_CATEGORIES
            for char in description
        ):
            raise forms.ValidationError("Enter an expense description.")
        return description

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("is_fixed"):
            # Only fixed expenses repeat. A variable expense never keeps a
            # schedule, even one left in the form before switching to Variable.
            cleaned_data["recurrence"] = Transaction.Recurrence.NONE
            cleaned_data["next_due_date"] = None
        elif cleaned_data.get("recurrence") and not cleaned_data.get("next_due_date"):
            if "next_due_date" not in self.errors:
                self.add_error("next_due_date", "Choose the next due date.")
        elif cleaned_data.get("next_due_date") and not cleaned_data.get("recurrence"):
            self.add_error("recurrence", "Choose how often it repeats.")
        return cleaned_data


@login_required
def record_income(request):
    if request.method == "POST":
        form = IncomeForm(request.POST)
    else:
        form = IncomeForm(None)

    if request.method == "POST" and form.is_valid():
        income = form.save(commit=False)
        income.kind = Transaction.Kind.INCOME
        income.owner = request.user
        income.save()
        messages.success(request, "Income saved.")
        return redirect("record_income")

    return render(request, "transactions/record_income.html", {"form": form})


@login_required
def record_expense(request):
    if request.method == "POST":
        form = ExpenseForm(request.POST)
    else:
        form = ExpenseForm(None)

    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.kind = Transaction.Kind.EXPENSE
        expense.owner = request.user
        expense.save()
        messages.success(request, "Expense saved.")
        return redirect("record_expense")

    return render(request, "transactions/record_expense.html", {"form": form})


@login_required
def edit_transaction(request, pk):
    # Only the owner can edit a real transaction.
    transaction = get_object_or_404(
        Transaction,
        pk=pk,
        owner=request.user,
        is_demo=False,
    )

    form_class = (
        IncomeForm
        if transaction.kind == Transaction.Kind.INCOME
        else ExpenseForm
    )

    if request.method == "POST":
        form = form_class(request.POST, instance=transaction)

        if form.is_valid():
            form.save()
            messages.success(request, "Transaction updated.")
            return redirect("dashboard")
    else:
        initial = {}

        # The expense form expects "fixed"/"variable", not a Boolean.
        if transaction.kind == Transaction.Kind.EXPENSE:
            initial["is_fixed"] = (
                "fixed" if transaction.is_fixed else "variable"
            )

        form = form_class(instance=transaction, initial=initial)

    return render(
        request,
        "transactions/edit_transaction.html",
        {"form": form, "transaction": transaction},
    )


@login_required
def delete_transaction(request, pk):
    # Only the owner can delete a non-demo transaction.
    transaction = get_object_or_404(
        Transaction,
        pk=pk,
        owner=request.user,
        is_demo=False,
    )

    if request.method == "POST":
        transaction.delete()
        messages.success(request, "Transaction deleted.")
        return redirect("dashboard")

    return render(
        request,
        "transactions/delete_transaction.html",
        {"transaction": transaction},
    )


def month_from_query(value):
    """Return the first day of a "YYYY-MM" month, or of the current month when
    the value is missing or invalid. Uses the same rules as the dashboard."""
    current_month = timezone.localdate().replace(day=1)
    if len(value) != 7 or value[4] != "-":
        return current_month
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError:
        return current_month


@login_required
def spending_by_category(request):
    month = month_from_query(request.GET.get("month", ""))

    # One row per category with its total, largest first. Equal totals are
    # ordered by name so the chart never reshuffles between page loads.
    totals = list(
        Transaction.objects.filter(
            owner=request.user,
            is_demo=False,
            kind=Transaction.Kind.EXPENSE,
            date__year=month.year,
            date__month=month.month,
        )
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total", "category")
    )

    # Each bar's length is its share of the largest category, kept as exact
    # decimals and formatted here so the template only places the value.
    largest = totals[0]["total"] if totals else None
    categories = [
        {
            "category": row["category"],
            "total": row["total"],
            "width": f"{row['total'] * 100 / largest:.2f}",
        }
        for row in totals
    ]

    return render(
        request,
        "transactions/spending_by_category.html",
        {
            "categories": categories,
            "month": month,
            "selected_month": f"{month:%Y-%m}",
        },
    )
