"""Aurora connection checks using mocks; no AWS calls or database needed."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgetwise.settings")

from budgetwise.db.aurora.base import DatabaseWrapper, PostgreSQLWrapper


class DatabaseTests(unittest.TestCase):
    def test_each_connection_gets_a_fresh_token(self):
        backend = DatabaseWrapper({})
        backend.rds_client = Mock()
        backend.rds_client.generate_db_auth_token.side_effect = ["first", "second"]
        params = {"host": "example.invalid", "port": "5432", "user": "app"}
        with patch.object(PostgreSQLWrapper, "get_new_connection") as connect:
            backend.get_new_connection(params)
            backend.get_new_connection(params)
        self.assertEqual(
            [call.args[0]["password"] for call in connect.call_args_list],
            ["first", "second"],
        )
        self.assertNotIn("password", params)
        backend.rds_client.generate_db_auth_token.assert_called_with(
            DBHostname="example.invalid", Port=5432, DBUsername="app"
        )

    def test_authentication_failure_does_not_open_a_connection(self):
        backend = DatabaseWrapper({})
        backend.rds_client = Mock()
        backend.rds_client.generate_db_auth_token.side_effect = RuntimeError("No credentials")
        with patch.object(PostgreSQLWrapper, "get_new_connection") as connect:
            with self.assertRaises(RuntimeError):
                backend.get_new_connection({"host": "example.invalid", "port": "5432", "user": "app"})
        connect.assert_not_called()

    def test_local_default_and_explicit_aurora_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            from budgetwise import settings

            importlib.reload(settings)
            self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3")
            os.environ.update(DB_HOST="example.invalid", DB_NAME="budgetwise", DB_USER="app")
            importlib.reload(settings)
            database = settings.DATABASES["default"]
            self.assertEqual(database["ENGINE"], "budgetwise.db.aurora")
            self.assertEqual(database["OPTIONS"]["sslmode"], "verify-full")
            self.assertTrue(Path(database["OPTIONS"]["sslrootcert"]).is_file())
            self.assertEqual(database["CONN_MAX_AGE"], 0)
            del os.environ["DB_USER"]
            with self.assertRaises(KeyError):
                importlib.reload(settings)
        importlib.reload(settings)


if __name__ == "__main__":
    unittest.main()
