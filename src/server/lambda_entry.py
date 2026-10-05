"""Run Django behind API Gateway using Lambda's event format."""
import os

from django.conf import settings
from mangum import Mangum

# Refuse to use the local development signing key in Lambda.
if len(os.environ.get("DJANGO_SECRET_KEY", "")) < 50:
    raise RuntimeError("A deployment signing key is required")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgetwise.settings")

# Apply deployment settings before Django initializes; runserver is unaffected.
settings.DEBUG = False
settings.ALLOWED_HOSTS = ["budget-wise.dev"]
settings.CSRF_TRUSTED_ORIGINS = ["https://budget-wise.dev"]
settings.SECURE_SSL_REDIRECT = True
settings.SESSION_COOKIE_SECURE = True
settings.CSRF_COOKIE_SECURE = True
settings.SECURE_CONTENT_TYPE_NOSNIFF = True

from budgetwise.asgi import application

# Django handles HTTP but does not implement ASGI startup/shutdown events.
handler = Mangum(application, lifespan="off")
