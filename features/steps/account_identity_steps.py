"""Issue #10 foundation checks; mailbox verification is a caller precondition."""

import os
from pathlib import Path
import sys

from behave import given, then, when


PASSWORD = "A-tide-of-bright-copper-42!"


@given("the account foundation has an isolated database and already verified mailbox ownership")
def account_database(context):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgetwise.settings")

    import django

    django.setup()

    from django.test.runner import DiscoverRunner

    runner = DiscoverRunner(verbosity=0, interactive=False)
    runner.setup_test_environment()
    context.add_cleanup(runner.teardown_test_environment)
    databases = runner.setup_databases()
    context.add_cleanup(runner.teardown_databases, databases)


@when('the account foundation creates "{email}" with a valid password')
def create_account(context, email):
    from accounts.identity import create_verified_user

    context.account = create_verified_user(email, PASSWORD)


@then('the account foundation stores "{email}" as one active ordinary identity')
def ordinary_identity(context, email):
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get()
    assert user.username == user.email == email
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert user.password != PASSWORD and user.check_password(PASSWORD)


@then("Django can authenticate that account foundation identity")
def authenticate_identity(context):
    from django.contrib.auth import authenticate

    assert authenticate(username=context.account.username, password=PASSWORD) == context.account


@when("the account foundation receives a seven-character password")
def short_password(context):
    from django.core.exceptions import ValidationError
    from accounts.identity import create_verified_user

    context.account_rejected = False
    try:
        create_verified_user("student@example.com", "Ab3!xyZ")
    except ValidationError:
        context.account_rejected = True


@then("the account foundation rejects it without creating a user")
def rejected_account(context):
    from django.contrib.auth import get_user_model

    assert context.account_rejected
    assert get_user_model().objects.count() == 0


@when("the account foundation tries a case and whitespace variant with a different password")
def duplicate_identity(context):
    from django.db import IntegrityError
    from accounts.identity import create_verified_user

    context.account_duplicate = False
    try:
        create_verified_user("  STUDENT@EXAMPLE.COM  ", "A-different-copper-tide-71!")
    except IntegrityError:
        context.account_duplicate = True


@then("the account foundation retains one user with the original password")
def original_account(context):
    from django.contrib.auth import get_user_model

    assert context.account_duplicate
    user = get_user_model().objects.get()
    assert user.pk == context.account.pk
    assert user.username == user.email == "student@example.com"
    assert user.check_password(PASSWORD)


@when('a Django user is saved with username "{username}" and email "{email}"')
def direct_account(context, username, email):
    from django.contrib.auth import get_user_model

    context.account = get_user_model().objects.create(username=username, email=email)


@when('another username tries to use "{email}"')
def duplicate_email(context, email):
    from django.contrib.auth import get_user_model
    from django.db import IntegrityError, transaction

    context.account_duplicate = False
    try:
        with transaction.atomic():
            get_user_model().objects.create(username="second-account", email=email)
    except IntegrityError:
        context.account_duplicate = True


@then("the database rejects the duplicate email and keeps the first user")
def original_email_owner(context):
    from django.contrib.auth import get_user_model

    assert context.account_duplicate
    user = get_user_model().objects.get()
    assert user.pk == context.account.pk
    assert user.username == "first-account" and user.email == "Student@Example.COM"
