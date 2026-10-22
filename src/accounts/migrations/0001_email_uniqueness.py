"""Enforce email identity uniqueness on Django's existing auth.User table."""

from django.db import migrations


def enforce_email_identity(apps, schema_editor):
    # auth.User belongs to Django, so this app owns only the additional SQL objects.
    table = schema_editor.quote_name(apps.get_model("auth", "User")._meta.db_table)
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(f"""
            ALTER TABLE {table} ADD CONSTRAINT accounts_email_ascii
            CHECK (email COLLATE "C" !~ '[^ -~]'
                   AND (email = '' OR TRIM(email) <> ''))
        """)
        identity = 'LOWER(TRIM(email) COLLATE "C")'
    elif vendor == "sqlite":
        # SQLite cannot add a CHECK without rebuilding auth_user. These guards
        # also reject NUL, which SQLite's text pattern matching would truncate.
        for event in ("INSERT", "UPDATE OF email"):
            suffix = "insert" if event == "INSERT" else "update"
            schema_editor.execute(f"""
                CREATE TRIGGER accounts_email_ascii_{suffix}
                BEFORE {event} ON {table}
                WHEN NEW.email GLOB '*[^ -~]*' OR INSTR(NEW.email, CHAR(0)) > 0
                     OR (NEW.email <> '' AND TRIM(NEW.email) = '')
                BEGIN
                    SELECT RAISE(ABORT, 'Email must be empty or nonblank printable ASCII');
                END
            """)
        identity = "LOWER(TRIM(email))"
    else:
        raise NotImplementedError("Email identity requires SQLite or PostgreSQL")
    # Match the helper's DNS root-dot removal. NULL permits accounts with no email.
    schema_editor.execute(f"""
        CREATE UNIQUE INDEX accounts_email_identity_unique
        ON {table} (RTRIM(NULLIF({identity}, ''), '.'))
    """)


class Migration(migrations.Migration):
    initial = True
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(enforce_email_identity)]
