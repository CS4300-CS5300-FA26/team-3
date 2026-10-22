from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.identity import normalize_email
from transactions.models import Transaction
from .lockout import check_login


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


# Require login before accessing the dashboard
@login_required(login_url="sign_in")
def dashboard(request):

    # Get only the current user's transactions
    transactions = Transaction.objects.filter(
        owner=request.user,
        is_demo=False,
    )

    # Display the dashboard with the user's transactions
    return render(
        request,
        "accounts/dashboard.html",
        {"transactions": transactions},
    )