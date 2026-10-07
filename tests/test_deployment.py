"""Exercise the CD workflow's failure paths without contacting GitHub or AWS."""
import base64
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ReadTimeoutError


def workflow_script(name):
    # Read the actual inline script so tests cannot drift from the workflow.
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/cd.yml").read_text()
    step = workflow.split(f"      - name: {name}\n", 1)[1]
    step = re.split(r"\n      - ", step, maxsplit=1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


class DeploymentTests(unittest.TestCase):
    def test_only_current_main_can_deploy(self):
        script = workflow_script("Reject stale deployment")
        # Replace gh with a shell function; exercise both a stale run and an API failure.
        stub = 'gh() { echo "$TEST_MAIN_SHA"; return "$TEST_API_STATUS"; };\n'
        for remote, status, expected in (("current", "0", 0), ("newer", "0", 1), ("", "1", 1)):
            with self.subTest(remote=remote, status=status):
                env = dict(os.environ, GITHUB_SHA="current", GITHUB_REPOSITORY="example/repo",
                           TEST_MAIN_SHA=remote, TEST_API_STATUS=status)
                result = subprocess.run(["bash", "-e", "-c", stub + script], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)

    def run_release(self, client, public_status=404):
        script = workflow_script("Publish, check, and promote")
        code = script.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "budgetwise.zip").write_bytes(b"test package")
            response = MagicMock()
            response.__enter__.return_value.status = public_status
            with patch.dict(os.environ, RUNNER_TEMP=directory, ROOT_STATUS="404", GITHUB_SHA="current"), \
                 patch("boto3.client", return_value=client), \
                 patch("urllib.request.urlopen", return_value=response), patch("builtins.print"):
                exec(compile(code, "cd.yml", "exec"), {})

    def client(self):
        client = MagicMock()
        client.get_alias.return_value = {"FunctionVersion": "1", "RevisionId": "previous"}
        config = {"RevisionId": "original-config", "Runtime": "python3.13",
                  "Environment": {"Variables": {"DB_NAME": "budgetwise"}}}
        latest = dict(config, RevisionId="verified-config", State="Active",
                      LastUpdateStatus="Successful",
                      CodeSha256=base64.b64encode(hashlib.sha256(b"test package").digest()).decode())
        client.get_function_configuration.side_effect = [config, latest]
        client.update_function_code.return_value = {"RevisionId": "uploaded-config"}
        client.publish_version.return_value = {"Version": "2"}
        client.update_alias.return_value = {"FunctionVersion": "2", "RevisionId": "promoted"}
        client.invoke.side_effect = [
            {"Payload": io.BytesIO(b'{"database":"ok"}')},
            {"Payload": io.BytesIO(b'{"statusCode":404}')},
        ]
        return client

    def test_publication_uses_verified_revision(self):
        client = self.client()
        self.run_release(client)
        self.assertEqual(client.publish_version.call_args.kwargs["RevisionId"], "verified-config")
        self.assertEqual(client.update_alias.call_args.kwargs["RevisionId"], "previous")

    def test_unverified_function_never_publishes_or_promotes(self):
        for changes in (
            {"State": "Pending"}, {"State": "Failed"},
            {"LastUpdateStatus": "InProgress"}, {"LastUpdateStatus": "Failed"},
            {"CodeSha256": "different-package"}, {"Runtime": "python3.14"},
            {"Environment": {"Variables": {"DB_NAME": "other"}}},
        ):
            with self.subTest(changes=changes):
                client = self.client()
                config, latest = list(client.get_function_configuration.side_effect)
                latest.update(changes)
                client.get_function_configuration.side_effect = [config, latest]
                with self.assertRaises(RuntimeError):
                    self.run_release(client)
                client.publish_version.assert_not_called()
                client.update_alias.assert_not_called()

    def test_failed_candidate_never_moves_live(self):
        client = self.client()
        client.invoke.side_effect = [{"FunctionError": "Unhandled"}]
        with self.assertRaises(RuntimeError):
            self.run_release(client)
        client.update_alias.assert_not_called()

    def test_lost_promotion_response_still_checks_and_rolls_back(self):
        client = self.client()
        client.get_alias.side_effect = [
            {"FunctionVersion": "1", "RevisionId": "previous"},
            {"FunctionVersion": "2", "RevisionId": "promoted"},
        ]
        client.update_alias.side_effect = [ReadTimeoutError(endpoint_url="test"), {}]
        with self.assertRaisesRegex(RuntimeError, "Public URL"):
            self.run_release(client, public_status=500)
        self.assertEqual(client.update_alias.call_count, 2)
        self.assertEqual(client.update_alias.call_args.kwargs["FunctionVersion"], "1")
        self.assertEqual(client.update_alias.call_args.kwargs["RevisionId"], "promoted")

    def test_failed_or_concurrent_promotion_is_not_overwritten(self):
        for current in (
            {"FunctionVersion": "1", "RevisionId": "previous"},
            {"FunctionVersion": "3", "RevisionId": "other"},
            {"FunctionVersion": "2", "RevisionId": "other", "RoutingConfig": {
                "AdditionalVersionWeights": {"3": 0.5}}},
        ):
            with self.subTest(current=current):
                client = self.client()
                client.get_alias.side_effect = [client.get_alias.return_value, current]
                client.update_alias.side_effect = ReadTimeoutError(endpoint_url="test")
                with self.assertRaises(ReadTimeoutError):
                    self.run_release(client)
                client.update_alias.assert_called_once()

    def test_lost_rollback_response_is_reconciled(self):
        client = self.client()
        client.get_alias.side_effect = [
            {"FunctionVersion": "1", "RevisionId": "previous"},
            {"FunctionVersion": "1", "RevisionId": "restored"},
        ]
        client.update_alias.side_effect = [
            {"FunctionVersion": "2", "RevisionId": "promoted"},
            ReadTimeoutError(endpoint_url="test"),
        ]
        with self.assertRaisesRegex(RuntimeError, "Public URL"):
            self.run_release(client, public_status=500)
        self.assertEqual(client.get_alias.call_count, 2)
