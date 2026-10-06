"""Use the disposable PostgreSQL service on the CI runner, never Aurora."""
import os

from .settings import *  # noqa: F403

# These credentials exist only in the temporary CI database and are not secrets.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "127.0.0.1",
        "PORT": os.environ.get("CI_DB_PORT", "5432"),
        "NAME": "budgetwise_ci",
        "USER": "postgres",
        "PASSWORD": "ci-only",
        "OPTIONS": {"connect_timeout": 5},
    }
}
