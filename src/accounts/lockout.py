from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import connection, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import FailedSignIn, LoginAttempt, SignInBudget


SIGN_IN_LIMIT = 100
SOURCE_LIMIT = 10


class SignInRateLimited(Exception):
    pass


def claim_sign_in_request(remote_address):
    """Admit sources fairly within one bounded, shared minute counter."""
    source = salted_hmac("accounts.signin.source", remote_address, algorithm="sha256").hexdigest()
    with transaction.atomic():
        if connection.vendor == "sqlite":
            SignInBudget.objects.filter(pk=1).update(requests=F("requests"))
        now = timezone.now()
        budget, created = SignInBudget.objects.select_for_update().get_or_create(
            pk=1, defaults={"resets_at": now + timedelta(minutes=1)},
        )
        if created or budget.resets_at <= now:
            budget.requests = 0
            budget.sources = {}
            budget.resets_at = now + timedelta(minutes=1)
            cleanup_stale_attempts()
        if budget.sources.get(source, 0) >= SOURCE_LIMIT or budget.requests >= SIGN_IN_LIMIT:
            return False
        budget.sources[source] = budget.sources.get(source, 0) + 1
        budget.requests += 1
        budget.save()
        return True


def cleanup_stale_attempts():
    """Expire failure history and idle identities without clearing active locks."""
    now = timezone.now()
    cutoff = now - timedelta(minutes=15)
    with transaction.atomic():
        # Match sign-in lock order: parent first, then failure history.
        LoginAttempt.objects.filter(
            Q(first_failed_at__isnull=True) | Q(first_failed_at__lte=cutoff),
            Q(blocked_until__isnull=True) | Q(blocked_until__lte=now),
        ).delete()
        FailedSignIn.objects.filter(created_at__lte=cutoff).delete()


def check_login(request, email, password):
    # REMOTE_ADDR comes from the server/API Gateway, never a forwarded header.
    if not claim_sign_in_request(request.META.get("REMOTE_ADDR", "")):
        raise SignInRateLimited
    with transaction.atomic():
        if connection.vendor == "sqlite":
            # SQLite has no row locks. Take its write lock before reading so
            # concurrent connections serialize the whole check and update.
            LoginAttempt.objects.filter(email=email).update(email=F("email"))

        # Lock as part of the lookup: cleanup may delete an idle row before
        # this query, in which case get_or_create safely creates its replacement.
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(email=email)
        now = timezone.now()
        if attempt.blocked_until and attempt.blocked_until > now:
            return None, True

        user = authenticate(request, username=email, password=password)
        if user is not None:
            FailedSignIn.objects.filter(email=email).delete()
            attempt.failed_count = 0
            attempt.first_failed_at = None
            attempt.blocked_until = None
        else:
            now = timezone.now()
            cutoff = now - timedelta(minutes=15)
            FailedSignIn.objects.filter(email=email, created_at__lte=cutoff).delete()
            FailedSignIn.objects.create(email=email, created_at=now)
            attempt.failed_count = FailedSignIn.objects.filter(
                email=email, created_at__gt=cutoff,
            ).count()
            if attempt.failed_count >= 5:
                attempt.blocked_until = now + timedelta(minutes=15)
            attempt.first_failed_at = now
        attempt.save()
        return user, False
