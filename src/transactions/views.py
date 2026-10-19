from datetime import date
from decimal import Decimal

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
