from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Max, Min, Q, Sum
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.forms import SetPasswordForm, SignupForm
from accounts.identity import normalize_email
from accounts.lockout import SignInRateLimited, check_login
from accounts.models import LowBalanceThreshold
from accounts.signup import send_signup_email
from accounts.verification import complete_registration, email_from_verification_token
from transactions.models import Transaction


@sensitive_post_parameters("email")
@never_cache
@require_http_methods(["GET", "POST"])
@login_not_required
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            send_signup_email(form.cleaned_data["email"], request.META.get("REMOTE_ADDR", ""))
        except (SMTPException, OSError):
            form.add_error(None, "Unable to send email right now. Please try again later.")
        else:
            return redirect("accounts:check_email")
    return render(request, "accounts/registration.html", {"signup": True, "form": form})


@never_cache
@require_GET
@login_not_required
def check_email(request):
    return render(request, "accounts/registration.html", {"check_email": True})


@sensitive_post_parameters("password", "password_confirmation")
@never_cache
@require_http_methods(["GET", "POST"])
@login_not_required
def verify(request, token):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SetPasswordForm(request.POST if request.method == "POST" else None)
    invalid_link = False
    email = None
    try:
        email = email_from_verification_token(token)
    except (signing.BadSignature, ValidationError):
        invalid_link = True
    if not invalid_link and request.method == "POST" and form.is_valid():
        try:
            complete_registration(token, **form.cleaned_data)
        except (signing.BadSignature, IntegrityError):
            invalid_link = True
        except ValidationError as error:
            form.add_error(None, error)
        else:
            response = redirect("accounts:created")
            response["Referrer-Policy"] = "same-origin"
            return response
    response = render(request, "accounts/registration.html", {
        "form": form, "invalid_link": invalid_link,
        "email": email if not invalid_link else None,
    }, status=400 if invalid_link else 200)
    response["Referrer-Policy"] = "same-origin"
    return response


@require_GET
@login_not_required
def created(request):
    return render(request, "accounts/registration.html", {
        "created": True, "sign_in_url": resolve_url(settings.LOGIN_URL),
    })


@sensitive_post_parameters("email", "password")
@never_cache
@require_http_methods(["GET", "POST"])
@login_not_required
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = None
    # Resume only the protected pages that send users here. This also prevents
    # external redirects and loops through signup, sign-in, or sign-out.
    destination = request.POST.get("next", request.GET.get("next", ""))
    if destination not in {
        reverse(name)
        for name in ("dashboard", "record_income", "record_expense", "spending_by_category")
    }:
        destination = reverse("dashboard")

    # Check if the sign in form was submitted
    if request.method == "POST":
        email = request.POST.get("email", "")
        password = request.POST.get("password", "")

        # Normalize the email before authentication
        try:
            email = normalize_email(email)
        except ValidationError:
            email = None

        # Check the login credentials and lockout status
        if email is not None:
            try:
                user, blocked = check_login(request, email, password)
            except SignInRateLimited:
                response = render(request, "accounts/sign_in.html", {
                    "error": "Too many sign-in requests. Try again in a minute.",
                    "next": destination,
                }, status=429)
                response["Retry-After"] = "60"
                return response
        else:
            user, blocked = None, False

        # Show the lockout message
        if blocked:
            error = "Too many attempts. Try again in 15 minutes."

        # Sign in if the credentials are correct
        elif user is not None:
            login(request, user)
            return redirect(destination)

        # Show an error for incorrect credentials
        else:
            error = "Email or password is incorrect"

    # Display the sign in page
    return render(
        request,
        "accounts/sign_in.html",
        {"error": error, "next": destination},
    )


# Only allow sign out through a POST request
@require_POST
def sign_out(request):
    logout(request)
    return redirect("sign_in")


class LowBalanceThresholdForm(forms.ModelForm):
    class Meta:
        model = LowBalanceThreshold
        fields = ["amount"]
        labels = {"amount": "Safety threshold ($)"}
        widgets = {"amount": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}


# Show the current user's monthly budget dashboard
@never_cache
@login_required(login_url="sign_in")
def dashboard(request):
    # Default to the current calendar month
    selected_month = timezone.localdate().replace(day=1)
    month_value = request.GET.get("month", "")

    # Allow the user to select a different month
    if month_value:
        try:
            if len(month_value) != 7 or month_value[4] != "-":
                raise ValueError("Month must use YYYY-MM format.")

            selected_month = date.fromisoformat(f"{month_value}-01")
        except ValueError:
            pass

    today = timezone.localdate()
    period_options = {
        "selected_month": f"Selected month ({selected_month:%B %Y})",
        "last_3_days": "Last 3 days",
        "last_7_days": "Last 7 days",
        "last_14_days": "Last 14 days",
        "this_month": "This month",
        "this_quarter": "This quarter",
        "all": "All time",
    }
    selected_period = request.GET.get("period", "selected_month")
    if selected_period not in period_options:
        selected_period = "selected_month"

    current_threshold = LowBalanceThreshold.objects.filter(owner=request.user).first()
    threshold_form = LowBalanceThresholdForm(
        request.POST if request.method == "POST" else None,
        instance=current_threshold,
    )
    if request.method == "POST" and threshold_form.is_valid():
        LowBalanceThreshold.objects.update_or_create(
            owner=request.user,
            defaults={"amount": threshold_form.cleaned_data["amount"]},
        )
        redirect_url = f"{reverse('dashboard')}?month={selected_month:%Y-%m}"
        if selected_period != "selected_month":
            redirect_url += f"&period={selected_period}"
        return redirect(redirect_url)

    # Keep the monthly budget independent from the transaction-history filter.
    budget_transactions = Transaction.objects.filter(
        owner=request.user,
        is_demo=False,
        date__year=selected_month.year,
        date__month=selected_month.month,
    )

    transactions = Transaction.objects.filter(owner=request.user, is_demo=False)
    if selected_period == "selected_month":
        period_start = selected_month
        period_end = date(
            selected_month.year,
            selected_month.month,
            monthrange(selected_month.year, selected_month.month)[1],
        )
        transactions = transactions.filter(
            date__year=selected_month.year,
            date__month=selected_month.month,
        )
    elif selected_period.startswith("last_"):
        days = int(selected_period.split("_")[1])
        period_start = today - timedelta(days=days - 1)
        period_end = today
        transactions = transactions.filter(
            date__gte=period_start, date__lte=period_end
        )
    elif selected_period == "this_month":
        period_start = today.replace(day=1)
        period_end = today
        transactions = transactions.filter(
            date__gte=period_start, date__lte=period_end
        )
    elif selected_period == "this_quarter":
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        period_start = date(today.year, quarter_start_month, 1)
        period_end = today
        transactions = transactions.filter(
            date__gte=period_start, date__lte=period_end
        )
    else:
        period_start = None
        period_end = None
    transactions = transactions.order_by("-date", "-id")

    period_totals = transactions.aggregate(
        income_total=Sum("amount", filter=Q(kind=Transaction.Kind.INCOME)),
        expense_total=Sum("amount", filter=Q(kind=Transaction.Kind.EXPENSE)),
        first_date=Min("date"),
        last_date=Max("date"),
    )
    income_total = period_totals["income_total"] or Decimal("0.00")
    expense_total = period_totals["expense_total"] or Decimal("0.00")
    if selected_period == "all":
        period_start = period_totals["first_date"]
        period_end = period_totals["last_date"]

    # Calculate the remaining balance using existing model logic
    remaining_budget = sum(
        (item.signed_amount for item in budget_transactions),
        Decimal("0.00"),
    )
    show_low_balance_warning = (
        current_threshold is not None and remaining_budget < current_threshold.amount
    )
    return render(
        request,
        "accounts/dashboard.html",
        {
            "transactions": transactions,
            "income_total": income_total,
            "expense_total": expense_total,
            "selected_period": selected_period,
            "period_options": period_options,
            "period_start": period_start,
            "period_end": period_end,
            "remaining_budget": remaining_budget,
            "selected_month": selected_month.isoformat()[:7],
            "selected_month_label": selected_month.strftime("%B %Y"),
            "budget_transaction_count": budget_transactions.count(),
            "current_threshold": current_threshold,
            "threshold_form": threshold_form,
            "show_low_balance_warning": show_low_balance_warning,
        },
    )
