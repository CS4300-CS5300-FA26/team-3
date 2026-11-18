from calendar import monthrange
from datetime import date, timedelta
import unicodedata
import tempfile
from pathlib import Path
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .services.receipt_scanner import scan_receipt
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
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


def _advance_paid_fixed_schedule(expense):
    """Match one pending schedule to a recorded payment without another user step."""
    if not expense.is_fixed or expense.recurrence != Transaction.Recurrence.NONE:
        return

    matches = [
        schedule
        for schedule in (
            Transaction.objects.select_for_update()
            .filter(
                owner=expense.owner,
                kind=Transaction.Kind.EXPENSE,
                is_fixed=True,
                is_demo=False,
                recurrence__in=[
                    Transaction.Recurrence.DAILY,
                    Transaction.Recurrence.WEEKLY,
                    Transaction.Recurrence.MONTHLY,
                ],
                amount=expense.amount,
                description__iexact=expense.description,
                category=expense.category,
                next_due_date__range=(expense.date, expense.date + timedelta(days=30)),
            )
            .order_by("next_due_date", "id")
        )
        if (schedule.next_due_date - expense.date).days <= schedule.reminder_days
    ]
    # A payment without a unique match must not move another schedule.
    if len(matches) != 1:
        return

    schedule = matches[0]
    due = schedule.next_due_date
    if schedule.recurrence == Transaction.Recurrence.DAILY:
        schedule.next_due_date = due + timedelta(days=1)
    elif schedule.recurrence == Transaction.Recurrence.WEEKLY:
        schedule.next_due_date = due + timedelta(days=7)
    else:
        year = due.year + (due.month == 12)
        month = due.month % 12 + 1
        schedule.next_due_date = date(
            year, month, min(due.day, monthrange(year, month)[1])
        )
    schedule.save(update_fields=["next_due_date"])


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
    reminder_days = forms.IntegerField(
        label="Remind me (days before due)",
        min_value=1,
        max_value=30,
        required=False,
        initial=3,
        widget=forms.NumberInput(attrs={"min": 1, "max": 30}),
    )

    class Meta:
        model = Transaction
        fields = [
            "amount", "date", "description", "category", "is_fixed",
            "recurrence", "next_due_date", "reminder_days",
        ]
        labels = {
            "amount": "Amount ($)", "description": "Description",
            "next_due_date": "Next due date",
        }
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
            for name in ("recurrence", "next_due_date", "reminder_days"):
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
        if (
            cleaned_data.get("reminder_days") is None
            and "reminder_days" not in self.errors
        ):
            cleaned_data["reminder_days"] = 3
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
        if not cleaned_data.get("recurrence"):
            cleaned_data["reminder_days"] = 3
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
        with transaction.atomic():
            expense.save()
            _advance_paid_fixed_schedule(expense)
        messages.success(request, "Expense saved.")
        return redirect("record_expense")

    return render(request, "transactions/record_expense.html", {"form": form})



@login_required
@require_POST
def scan_receipt_upload(request):
    """
    Accept a receipt image and return its detected total.

    The endpoint does not save or modify any transactions.
    """
    receipt = request.FILES.get("receipt")

    if receipt is None:
        return JsonResponse(
            {"error": "Please upload a receipt image."},
            status=400,
        )

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    extension = allowed_types.get(receipt.content_type)

    if extension is None:
        return JsonResponse(
            {"error": "Unsupported receipt image format."},
            status=400,
        )

    max_file_size = 5 * 1024 * 1024

    if receipt.size > max_file_size:
        return JsonResponse(
            {"error": "Receipt image must be 5 MB or smaller."},
            status=400,
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        image_path = Path(temp_dir) / f"receipt{extension}"

        with image_path.open("wb") as destination:
            for chunk in receipt.chunks():
                destination.write(chunk)

        # Verify that the uploaded file is a genuine supported image.
        allowed_formats = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }

        try:
            with Image.open(image_path) as image:
                actual_format = image.format
                image.verify()

            if actual_format != allowed_formats[receipt.content_type]:
                return JsonResponse(
                    {"error": "Unsupported receipt image format."},
                    status=400,
                )

            # Decode the image to catch corrupted image data.
            with Image.open(image_path) as image:
                image.load()

        except (UnidentifiedImageError, OSError, ValueError):
            return JsonResponse(
                {"error": "Invalid or corrupted receipt image."},
                status=400,
            )

        try:
            amount = scan_receipt(image_path)
        except RuntimeError:
            return JsonResponse(
                {"error": "Receipt scanning is currently unavailable."},
                status=503,
            )

    if amount is None:
        return JsonResponse(
            {
                "amount": None,
                "message": (
                    "Could not read a total, please enter it manually"
                ),
            }
        )

    return JsonResponse({"amount": str(amount)})


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
