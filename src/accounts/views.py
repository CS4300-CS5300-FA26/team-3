from smtplib import SMTPException

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from transactions.models import Transaction

from accounts.identity import normalize_email
from accounts.lockout import check_login

from accounts.forms import SetPasswordForm, SignupForm
from accounts.signup import send_signup_email
from accounts.verification import complete_registration, email_from_verification_token


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
    if destination not in {reverse(name) for name in ("dashboard", "record_income", "record_expense")}:
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
            user, blocked = check_login(request, email, password)
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
