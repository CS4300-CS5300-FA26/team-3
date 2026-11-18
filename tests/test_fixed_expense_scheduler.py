"""D14 (#28): a private Lambda event starts the daily reminder check."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


class FixedExpenseSchedulerTests(unittest.TestCase):
    def run_entry_point(self, script):
        # Import the Lambda entry point in a child process so its production
        # settings overrides cannot change other Django tests.
        env = dict(
            os.environ,
            DJANGO_SETTINGS_MODULE="budgetwise.settings",
            DJANGO_SECRET_KEY="local-test-only-" * 5,
            DB_HOST="",
            PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"),
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_private_event_runs_reminder_command_without_http(self):
        self.run_entry_point('''
from unittest.mock import patch
import lambda_entry

with patch("django.core.management.call_command") as command:
    with patch.object(lambda_entry, "http_handler") as http:
        result = lambda_entry.handler({"operation": "send_fixed_expense_reminders"}, None)
        assert result == {"reminders": "sent"}
        command.assert_called_once_with("send_fixed_expense_reminders")
        http.assert_not_called()
''')

    def test_http_shaped_event_cannot_start_the_private_check(self):
        self.run_entry_point('''
from unittest.mock import patch
import lambda_entry

event = {"operation": "send_fixed_expense_reminders", "requestContext": {}}
with patch("django.core.management.call_command") as command:
    with patch.object(lambda_entry, "http_handler", return_value={"http": "handled"}) as http:
        assert lambda_entry.handler(event, None) == {"http": "handled"}
        command.assert_not_called()
        http.assert_called_once_with(event, None)
''')

    def test_command_failure_closes_the_database_connection(self):
        self.run_entry_point('''
from unittest.mock import patch
import lambda_entry

with patch("django.core.management.call_command", side_effect=RuntimeError("mail failed")):
    with patch.object(lambda_entry.connection, "close") as close:
        with patch.object(lambda_entry, "http_handler") as http:
            try:
                lambda_entry.handler({"operation": "send_fixed_expense_reminders"}, None)
            except RuntimeError as error:
                assert str(error) == "mail failed"
            else:
                raise AssertionError("The reminder failure was hidden")
            close.assert_called_once_with()
            http.assert_not_called()
''')
