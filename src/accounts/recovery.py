"""Public D12 recovery pages and admission before per-email service work."""
from datetime import timedelta

from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN, PasswordResetConfirmView
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from accounts.forms import SignupForm
from accounts.models import PasswordResetBudget
from accounts.password_reset import complete_password_reset
from accounts.password_reset_requests import RESET_CONFIRMATION, request_password_reset


RESET_LIMIT = 100
SOURCE_LIMIT = 10


def claim_recovery_request(remote_address):
    """Bound distinct email work across workers using one rolling-hour row.

    Use the sign-in limiter's 100/10 global/source policy over the reset service's
    hour window. Keep independent budgets; no source keys are created on denial.
    """
    source = salted_hmac("accounts.reset.source", remote_address, algorithm="sha256").hexdigest()
    with transaction.atomic():
        if connection.vendor == "sqlite":
            PasswordResetBudget.objects.filter(pk=1).update(id=F("id"))
        budget, _ = PasswordResetBudget.objects.select_for_update().get_or_create(pk=1)
        now = timezone.now()  # Sample after acquiring the lock.
        cutoff = (now - timedelta(hours=1)).timestamp()
        recent = [entry for entry in budget.admitted_at if entry[0] > cutoff]
        if len(recent) >= RESET_LIMIT or sum(entry[1] == source for entry in recent) >= SOURCE_LIMIT:
            return False
        budget.admitted_at = [*recent, [now.timestamp(), source]]
        budget.save(update_fields=["admitted_at"])
    return True


@sensitive_post_parameters("email")
@never_cache
@require_http_methods(["GET", "POST"])
@login_not_required
def forgot_password(request):
    if request.method == "POST":
        # REMOTE_ADDR is supplied by the server/API Gateway, not forwarded headers.
        if claim_recovery_request(request.META.get("REMOTE_ADDR", "")):
            request_password_reset(request.POST.get("email", ""))
        return redirect("accounts:reset_sent")
    return render(request, "accounts/recovery.html", {"form": SignupForm(), "request_reset": True})


@never_cache
@require_GET
@login_not_required
def reset_sent(request):
    return render(request, "accounts/recovery.html", {"confirmation": RESET_CONFIRMATION})


@method_decorator([login_not_required, sensitive_post_parameters(), never_cache,
                   require_http_methods(["GET", "POST"])], name="dispatch")
class ResetPasswordView(PasswordResetConfirmView):
    """Reuse Django's token-to-session redirect, but commit through our core."""

    template_name = "accounts/recovery.html"
    success_url = reverse_lazy("accounts:reset_complete")

    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        response["Referrer-Policy"] = "same-origin"
        return response

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user and user.is_active and user.has_usable_password() else None

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["new_password2"].help_text = ""
        return form

    @sensitive_variables()
    def form_valid(self, form):
        try:
            complete_password_reset(
                self.user.pk, self.request.session[INTERNAL_RESET_SESSION_TOKEN],
                form.cleaned_data["new_password1"], form.cleaned_data["new_password2"],
            )
        except signing.BadSignature:
            self.validlink = False
            return self.render_to_response(self.get_context_data())
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        del self.request.session[INTERNAL_RESET_SESSION_TOKEN]
        return redirect(self.success_url)


@never_cache
@require_GET
@login_not_required
def reset_complete(request):
    return render(request, "accounts/recovery.html", {"complete": True})
