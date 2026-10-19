from datetime import date
from decimal import Decimal
import unicodedata

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Transaction


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["amount", "date", "description"]
        labels = {"amount": "Amount ($)", "description": "Source"}
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        error_messages = {
            "amount": {"min_value": "Amount must be greater than zero"},
            "description": {"required": "Enter an income source."},
        }


EXPENSE_CATEGORIES = ["Housing", "Food", "Books", "Transportation", "Other"]
INVISIBLE_CATEGORIES = {"Cc", "Cf", "Mn", "Me"}


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

    class Meta:
        model = Transaction
        fields = ["amount", "date", "description", "category", "is_fixed"]
        labels = {"amount": "Amount ($)", "description": "Description"}
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        error_messages = {
            "amount": {"min_value": "Amount must be greater than zero"},
            "description": {"required": "Enter an expense description."},
        }

    def clean_description(self):
        description = self.cleaned_data["description"]
        # These pass Django's whitespace strip but display as nothing on their own:
        # control (Cc) and format (Cf) characters such as a zero-width space, and
        # combining marks (Mn, Me) with no letter to attach to. Reject a description
        # made only of them; inside visible text they are kept as typed.
        if all(
            char.isspace() or unicodedata.category(char) in INVISIBLE_CATEGORIES
            for char in description
        ):
            raise forms.ValidationError("Enter an expense description.")
        return description


def transaction_list(request):
    """Show demo transactions and the remaining budget for one calendar month."""
    selected_month = timezone.localdate().replace(day=1)
    month_value = request.GET.get("month", "")
    if month_value:
        try:
            if len(month_value) != 7 or month_value[4] != "-":
                raise ValueError("Month must use YYYY-MM format.")
            selected_month = date.fromisoformat(f"{month_value}-01")
        except ValueError:
            # Invalid query parameters fall back to the current month.
            pass

    transactions = Transaction.objects.filter(
        is_demo=True,
        date__year=selected_month.year,
        date__month=selected_month.month,
    )
    remaining_budget = sum(
        (transaction.signed_amount for transaction in transactions),
        Decimal("0.00"),
    )

    return render(
        request,
        "transactions/transaction_list.html",
        {
            "transactions": transactions,
            "remaining_budget": remaining_budget,
            "selected_month": selected_month.isoformat()[:7],
            "period_start": selected_month,
        },
    )


@login_required
def record_income(request):
    if request.method == "POST":
        form = IncomeForm(request.POST)
    else:
        form = IncomeForm(None)

    if request.method == "POST" and form.is_valid():
        income = form.save(commit=False)
        income.kind = Transaction.Kind.INCOME
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
        expense.save()
        messages.success(request, "Expense saved.")
        return redirect("record_expense")

    return render(request, "transactions/record_expense.html", {"form": form})
