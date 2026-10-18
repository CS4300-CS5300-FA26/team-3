"""Issue #12 income acceptance checks using an isolated Django test database."""

import os
from pathlib import Path
import sys

from behave import given, then, when


@given("I am signed in to record income")
def signed_in(context):
    src = Path(__file__).resolve().parents[2] / "src"
    sys.path.insert(0, str(src))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgetwise.settings")

    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.test.runner import DiscoverRunner
    from transactions.models import Transaction

    runner = DiscoverRunner(verbosity=0, interactive=False)
    runner.setup_test_environment()
    context.add_cleanup(runner.teardown_test_environment)
    databases = runner.setup_databases()
    context.add_cleanup(runner.teardown_databases, databases)

    student = get_user_model().objects.create_user(username="student")
    context.client = Client()
    context.client.force_login(student)
    context.transaction_count = Transaction.objects.count()
    context.Transaction = Transaction


@when('I add income of ${amount} dated {date} with source "{source}"')
def add_income(context, amount, date, source):
    from django.urls import reverse

    context.response = context.client.post(
        reverse("record_income"),
        {"amount": amount, "date": date, "description": source},
    )


@then('I see "{message}"')
def see_message(context, message):
    assert context.response.status_code == 200
    assert message in context.response.content.decode(), f"Expected {message!r} in the response"


@then("no entry is created")
def no_entry(context):
    assert context.Transaction.objects.count() == context.transaction_count
