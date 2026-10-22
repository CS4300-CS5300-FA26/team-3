from datetime import timedelta
from django.contrib.auth import authenticate
from django.db import connection
from django.db import transaction
from django.utils import timezone
from .models import LoginAttempt, FailedSignIn


# Check whether an email is currently blocked
def is_blocked(email):
    attempt = LoginAttempt.objects.filter(email=email).first()

    return bool(
        attempt
        and attempt.blocked_until
        and attempt.blocked_until > timezone.now()
    )


# Record a failed sign in attempt
def record_failure(email):
    now = timezone.now()
    cutoff = now - timedelta(minutes=15)

    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(
            email=email
        )

        # Remove failures older than 15 minutes
        FailedSignIn.objects.filter(
            email=email,
            created_at__lte=cutoff,
        ).delete()

        # Save the new failed attempt
        FailedSignIn.objects.create(email=email, created_at=now)

        # Count failures within the last 15 minutes
        attempt.failed_count = FailedSignIn.objects.filter(
            email=email,
            created_at__gt=cutoff,
        ).count()

        # Block the email after five failures
        if attempt.failed_count >= 5:
            attempt.blocked_until = now + timedelta(minutes=15)

        attempt.first_failed_at = now
        attempt.save()


# Clear failures after a successful sign in
def clear_failures(email):
    with transaction.atomic():
        FailedSignIn.objects.filter(email=email).delete()
        LoginAttempt.objects.filter(email=email).delete()




# Remove expired individual failures without deleting login lock records
def cleanup_stale_attempts():
    now = timezone.now()
    cutoff = now - timedelta(minutes=15)

    FailedSignIn.objects.filter(
        created_at__lte=cutoff
    ).delete()



# Check credentials while protecting the login attempt record
def check_login(request, email, password):
    # SQLite cannot provide the required row-level lock
    if connection.vendor == "sqlite":
        if is_blocked(email):
            return None, True

        user = authenticate(
            request,
            username=email,
            password=password,
        )

        if user is not None:
            clear_failures(email)
        else:
            record_failure(email)

        return user, False

    # Lock the email record during authentication on PostgreSQL
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.get_or_create(email=email)

        attempt = LoginAttempt.objects.select_for_update().get(
            pk=attempt.pk
        )

        if attempt.blocked_until and attempt.blocked_until > timezone.now():
            return None, True

        user = authenticate(
            request,
            username=email,
            password=password,
        )

        if user is not None:
            # Clear failure history without deleting the locked row
            FailedSignIn.objects.filter(email=email).delete()
            attempt.failed_count = 0
            attempt.first_failed_at = None
            attempt.blocked_until = None
            attempt.save()
        else:
            now = timezone.now()
            cutoff = now - timedelta(minutes=15)

            # Remove expired failures
            FailedSignIn.objects.filter(
                email=email,
                created_at__lte=cutoff,
            ).delete()

            # Record the failed attempt
            FailedSignIn.objects.create(email=email, created_at=now)

            attempt.failed_count = FailedSignIn.objects.filter(
                email=email,
                created_at__gt=cutoff,
            ).count()

            if attempt.failed_count >= 5:
                attempt.blocked_until = now + timedelta(minutes=15)

            attempt.first_failed_at = now
            attempt.save()

        return user, False
