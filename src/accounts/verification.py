"""Single-use email verification for registration; tokens must not be logged.

Invalid/expired tokens raise signing.BadSignature, invalid email/password input
raises ValidationError, and duplicate accounts raise database IntegrityError.
Other database errors propagate unchanged. Tokens contain email, never passwords.
"""

from hashlib import sha256

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.identity import create_verified_user, normalize_email
from accounts.models import UsedVerificationToken


VERIFICATION_SALT = "accounts.registration.email-verification"
VERIFICATION_MAX_AGE = 24 * 60 * 60


def issue_verification_token(email):
    """Sign a canonical email without creating an account."""
    return signing.dumps(normalize_email(email), salt=VERIFICATION_SALT)


def email_from_verification_token(token):
    """Read a registration email only while its signature is valid for 24 hours."""
    if not isinstance(token, str):
        raise signing.BadSignature("Invalid verification token.")
    email = normalize_email(signing.loads(
        token, salt=VERIFICATION_SALT, max_age=VERIFICATION_MAX_AGE,
    ))
    if UsedVerificationToken.objects.filter(pk=token_digest(token)).exists():
        raise signing.BadSignature("Verification token has already been used.")
    return email


def complete_registration(token, password, password_confirmation):
    """Create a user without starting a session after token/password validation.

    The digest's unique key arbitrates concurrent attempts. Validation or database
    failures roll back consumption together with account creation.
    """
    email = email_from_verification_token(token)
    if password != password_confirmation:
        raise ValidationError("Passwords do not match.")
    with transaction.atomic():
        UsedVerificationToken.objects.create(digest=token_digest(token))
        return create_verified_user(email, password)


def token_digest(token):
    """Persist only a one-way fingerprint, never the signed email token."""
    return sha256(token.encode("utf-8")).hexdigest()
