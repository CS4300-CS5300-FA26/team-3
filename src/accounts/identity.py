"""Email normalization and account creation using Django authentication."""

import unicodedata

import idna

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction


def normalize_email(email):
    """Return the application's canonical email identity without writing data."""
    if not isinstance(email, str):
        raise ValidationError("Enter a valid email address.")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in email):
        raise ValidationError("Enter a valid email address.")
    local, separator, domain = email.strip().rpartition("@")
    if not separator or not local.isascii():
        raise ValidationError("Enter a valid email address.")
    try:
        # IP literals already have an ASCII representation; DNS names use IDNA2008.
        if not domain.startswith("["):
            domain = idna.encode(domain, uts46=True).decode("ascii").rstrip(".")
        canonical = f"{local}@{domain}".lower()
        canonical.encode("ascii")
    except (idna.IDNAError, UnicodeError) as error:
        raise ValidationError("Enter a valid email address.") from error
    if len(canonical) > 150:
        raise ValidationError("Email addresses must be at most 150 characters.")
    validate_email(canonical)
    return canonical


def create_verified_user(email, password):
    """Create an ordinary user only after the caller has verified email ownership.

    This internal helper does not verify ownership or start a session. Duplicate
    email identities or usernames raise IntegrityError after the inner transaction
    has rolled back.
    """
    canonical = normalize_email(email)
    if not isinstance(password, str) or not password:
        raise ValidationError("Enter a valid password.")
    user = get_user_model()(
        username=canonical, email=canonical,
        is_active=True, is_staff=False, is_superuser=False,
    )
    validate_password(password, user=user)
    user.set_password(password)
    # Email punctuation is valid here even when Django username validation rejects it.
    with transaction.atomic():
        user.save()
    return user
