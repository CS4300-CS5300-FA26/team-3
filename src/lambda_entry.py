"""Run Django behind API Gateway using Lambda's event format."""
import os

from django.conf import settings
from django.db import connection
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
http_handler = Mangum(application, lifespan="off")


def handler(event, context):
    # CD invokes this exact event through Lambda's authenticated API. Public
    # requests arrive in API Gateway's envelope and cannot select this branch.
    if event == {"operation": "check_database"}:
        try:
            if connection.vendor != "postgresql":
                raise RuntimeError("The deployed database must be PostgreSQL")
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise RuntimeError("Database check failed")
            return {"database": "ok"}
        finally:
            connection.close()
    return http_handler(event, context)
