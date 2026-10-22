"""Issue #10 signed-token core scenarios; no mail or UI integration."""

from unittest.mock import patch

from behave import then, when


PASSWORD = "A-tide-of-bright-copper-42!"


@when('the verification core issues a token for "{email}"')
def issue_token(context, email):
    from accounts.verification import issue_verification_token

    context.verification_token = issue_verification_token(email)


@then('the verification core reads "{email}" without creating a user')
def pending_identity(context, email):
    from django.contrib.auth import get_user_model
    from accounts.verification import email_from_verification_token

    assert email_from_verification_token(context.verification_token) == email
    assert get_user_model().objects.count() == 0


@when("the verification core completes registration with matching valid passwords")
def complete_account(context):
    from accounts.verification import complete_registration

    context.account = complete_registration(context.verification_token, PASSWORD, PASSWORD)


@when("the verification core receives a token older than 24 hours")
def expired_token(context):
    with patch("django.core.signing.time.time", return_value=1000000):
        issue_token(context, "student@example.com")


@then("the verification core rejects registration without creating a user")
def reject_expired(context):
    from django.contrib.auth import get_user_model
    from django.core import signing
    from accounts.verification import complete_registration

    with patch("django.core.signing.time.time", return_value=1086401):
        try:
            complete_registration(context.verification_token, PASSWORD, PASSWORD)
        except signing.SignatureExpired:
            pass
        else:
            raise AssertionError("Expired token was accepted")
    assert get_user_model().objects.count() == 0
