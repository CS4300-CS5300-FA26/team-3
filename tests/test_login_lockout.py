import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from transactions.models import Transaction
from accounts.models import LoginAttempt
from concurrent.futures import ThreadPoolExecutor


@pytest.mark.django_db
def test_lockout_after_five_failures(client):
    # Create a test user
    get_user_model().objects.create_user(
        username="test@example.com",
        email="test@example.com",
        password="TestPassword123!",
    )

    url = reverse("sign_in")

    # Submit five incorrect passwords
    for _ in range(5):
        response = client.post(url, {
            "email": "test@example.com",
            "password": "WrongPassword123",
        })

        assert b"Email or password is incorrect" in response.content

    # Confirm the email is now blocked
    attempt = LoginAttempt.objects.get(email="test@example.com")
    assert attempt.failed_count == 5

    # Confirm the correct password cannot bypass the lockout
    with patch("accounts.lockout.authenticate") as authenticate:
        response = client.post(url, {
            "email": "test@example.com",
            "password": "TestPassword123!",
        })

        authenticate.assert_not_called()

    assert b"Too many attempts. Try again in 15 minutes." in response.content


@pytest.mark.django_db
def test_lockout_expires(client):
    # Create a test user
    get_user_model().objects.create_user(
        username="test@example.com",
        email="test@example.com",
        password="TestPassword123!",
    )

    url = reverse("sign_in")

    # Simulate five failed sign in attempts
    for _ in range(5):
        client.post(url, {
            "email": "test@example.com",
            "password": "WrongPassword123",
        })

    # Move the lockout expiration into the past
    attempt = LoginAttempt.objects.get(email="test@example.com")
    attempt.blocked_until = timezone.now() - timedelta(seconds=1)
    attempt.save()

    # Try signing in with the correct password
    response = client.post(url, {
        "email": "test@example.com",
        "password": "TestPassword123!",
    })

    # Confirm sign in succeeds
    assert response.status_code == 302
    assert response.url == reverse("dashboard")

    # Confirm failed attempts are cleared
    assert not LoginAttempt.objects.filter(email="test@example.com").exists()


@pytest.mark.django_db
def test_lockout_is_separate_for_each_email(client):
    # Create two test users
    for email in ["user1@example.com", "user2@example.com"]:
        get_user_model().objects.create_user(
            username=email,
            email=email,
            password="TestPassword123!",
        )

    url = reverse("sign_in")

    # Fail five sign in attempts for the first user
    for _ in range(5):
        client.post(url, {
            "email": "user1@example.com",
            "password": "WrongPassword123",
        })

    # Confirm the first user is blocked
    response = client.post(url, {
        "email": "user1@example.com",
        "password": "TestPassword123!",
    })

    assert b"Too many attempts. Try again in 15 minutes." in response.content

    # Confirm the second user can still sign in
    response = client.post(url, {
        "email": "user2@example.com",
        "password": "TestPassword123!",
    })

    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    # Try opening the dashboard without signing in
    response = client.get(reverse("dashboard"))

    # Confirm the user is redirected to sign in
    assert response.status_code == 302
    assert response.url.startswith(reverse("sign_in"))


@pytest.mark.django_db
def test_dashboard_only_shows_own_transactions(client):
    # Create two users
    user1 = get_user_model().objects.create_user(
        username="user1@example.com",
        email="user1@example.com",
        password="TestPassword123!",
    )

    user2 = get_user_model().objects.create_user(
        username="user2@example.com",
        email="user2@example.com",
        password="TestPassword123!",
    )

    # Create transactions for each user
    # Create a transaction for the first user
    Transaction.objects.create(
        owner=user1,
        kind="expense",
        amount="25.00",
        date="2026-10-22",
        description="User 1 Purchase",
        category="Food",
    )

    # Create a transaction for the second user
    Transaction.objects.create(
        owner=user2,
        kind="expense",
        amount="50.00",
        date="2026-10-22",
        description="User 2 Purchase",
        category="Shopping",
    )

    # Sign in as the first user
    client.force_login(user1)

    # Open the dashboard
    response = client.get(reverse("dashboard"))

    assert response.status_code == 200

    # Confirm only the first user's transaction appears
    assert b"User 1 Purchase" in response.content
    assert b"User 2 Purchase" not in response.content


