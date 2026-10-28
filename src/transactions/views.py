import unicodedata

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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
