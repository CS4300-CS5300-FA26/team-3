"""The shared account email layout, configured origin and Django mail transport."""
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.views.decorators.debug import sensitive_variables


@sensitive_variables()
def send_account_email(email, subject, path, intro, action, details):
    link = urljoin(settings.SIGNUP_BASE_URL + "/", path)
    body = f"{intro}\n\n{action}:\n{link}\n\n{details}\n\nThe BudgetWise team\n"
    html = render_to_string("accounts/account_email.html", {
        "subject": subject, "intro": intro, "link": link, "action": action, "details": details,
    })
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], html_message=html)
