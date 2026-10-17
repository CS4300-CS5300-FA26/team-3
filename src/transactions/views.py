from django import forms
from django.shortcuts import render

from .models import Transaction


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["amount", "date", "description"]
        labels = {"description": "Source"}
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        error_messages = {
            "amount": {"min_value": "Amount must be greater than zero"},
        }


def transaction_list(request):
    """Render the landing page with transactions from the database."""
    transactions = Transaction.objects.filter(is_demo=True)

    return render(
        request,
        "transactions/transaction_list.html",
        {"transactions": transactions},
    )
