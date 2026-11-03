from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# Store failed sign in attempts for each email
class LoginAttempt(models.Model):
    email = models.CharField(max_length=254, unique=True)
    failed_count = models.PositiveIntegerField(default=0)
    first_failed_at = models.DateTimeField(null=True, blank=True)
    blocked_until = models.DateTimeField(null=True, blank=True)

# Store the time of each failed sign in attempt
class FailedSignIn(models.Model):
    email = models.CharField(max_length=254, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)


class UsedVerificationToken(models.Model):
    # No user link: deleting an account must never make its token reusable.
    digest = models.CharField(max_length=64, primary_key=True)
    consumed_at = models.DateTimeField(default=timezone.now, db_index=True)


class SignupRateLimit(models.Model):
    # HMAC keys avoid retaining raw recipient addresses or IP addresses.
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class PasswordResetRateLimit(models.Model):
    # HMAC email key and at most five admission timestamps; never reset tokens.
    key = models.CharField(max_length=64, primary_key=True)
    admitted_at = models.JSONField(default=list)
    expires_at = models.DateTimeField(db_index=True)


class SignInBudget(models.Model):
    # One shared row bounds work across email addresses and application workers.
    id = models.PositiveSmallIntegerField(primary_key=True)
    requests = models.PositiveIntegerField(default=0)
    sources = models.JSONField(default=dict)
    resets_at = models.DateTimeField()


class LowBalanceThreshold(models.Model):
    """An optional safety threshold belonging to one student."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="low_balance_threshold",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="low_balance_threshold_nonnegative",
            ),
        ]
