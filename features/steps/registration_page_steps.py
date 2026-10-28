from behave import then, when

from verification_steps import PASSWORD


@when("the student opens the verification page and submits matching valid passwords")
def register_through_page(context):
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.urls import reverse

    context.registration_client = Client()
    url = reverse("accounts:verify", args=[context.verification_token])
    assert context.registration_client.get(url).status_code == 200
    assert get_user_model().objects.count() == 0
    response = context.registration_client.post(url, {
        "password": PASSWORD, "password_confirmation": PASSWORD,
    })
    assert response.status_code == 302
    assert response.url == reverse("accounts:created")
    context.registration_success = context.registration_client.get(response.url)


@then("the student sees Account created and a Sign in button without being signed in")
def account_created_page(context):
    from django.conf import settings
    from django.shortcuts import resolve_url

    page = context.registration_success.content.decode()
    assert "Account created" in page
    assert f'href="{resolve_url(settings.LOGIN_URL)}"' in page
    assert ">Sign in</a>" in page
    assert "_auth_user_id" not in context.registration_client.session


@then("the verification link is no longer usable")
def used_link_is_rejected(context):
    from django.urls import reverse

    url = reverse("accounts:verify", args=[context.verification_token])
    assert context.registration_client.get(url).status_code == 400
