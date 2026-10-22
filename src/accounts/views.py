from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from datetime import date
from decimal import Decimal
from django.utils import timezone
from accounts.identity import normalize_email
from transactions.models import Transaction
from .lockout import check_login
from django.views.decorators.cache import never_cache


# Handle user sign in
def sign_in(request):
    error = None

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
            user, blocked = check_login(request, email, password)
        else:
            user, blocked = None, False

        # Show the lockout message
        if blocked:
            error = "Too many attempts. Try again in 15 minutes."

        # Sign in if the credentials are correct
        elif user is not None:
            login(request, user)
            return redirect("dashboard")

        # Show an error for incorrect credentials
        else:
            error = "Email or password is incorrect"

    # Display the sign in page
    return render(
        request,
        "accounts/sign_in.html",
        {"error": error},
    )


# Only allow sign out through a POST request
@require_POST
def sign_out(request):
    logout(request)
    return redirect("sign_in")


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

    # Get only this user's real transactions for the selected month
    transactions = Transaction.objects.filter(
        owner=request.user,
        is_demo=False,
        date__year=selected_month.year,
        date__month=selected_month.month,
    ).order_by("-date", "-id")

    # Calculate the remaining balance using existing model logic
    remaining_budget = sum(
        (item.signed_amount for item in transactions),
        Decimal("0.00"),
    )

    return render(
        request,
        "accounts/dashboard.html",
        {
            "transactions": transactions,
            "remaining_budget": remaining_budget,
            "selected_month": selected_month.isoformat()[:7],
        },
    )
