"""Review automation tests use fake GitHub/OpenAI boundaries; no paid calls."""
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github"))
from scripts import ai_review, check_coverage  # noqa: E402


class AIReviewTests(unittest.TestCase):
    def fixture(self):
        return {'head': {'sha': 'abc', 'repo': {'full_name': 'team/repo'}},
                'base': {'sha': 'base', 'ref': 'main'}, 'state': 'open',
                'draft': False, 'author_association': 'MEMBER', 'user': {'login': 'teammate'},
                'changed_files': 1, 'title': 'Change', 'body': 'Closes #12'}

    def test_collect_blocks_ineligible_current_pr_before_reading_changes(self):
        """#41 / PR #44: validate trust with current REST metadata."""
        cases = [('draft', True), ('draft', None), ('base', {'ref': 'other'}),
                 ('head', {'sha': 'abc', 'repo': {'full_name': 'other/repo'}}),
                 ('head', {'sha': 'abc', 'repo': None})]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                github = Mock(return_value=dict(self.fixture(), **{field: value}))
                with self.assertRaises(ValueError):
                    ai_review.collect(github, 44, 'team/repo', 'abc')
                self.assertEqual(github.call_count, 1)

    def test_author_eligibility_uses_repository_access_not_association(self):
        for permission in ('admin', 'write', 'read', 'none'):
            with self.subTest(permission=permission):
                pr = dict(self.fixture(), author_association='CONTRIBUTOR', body='')
                github = Mock(side_effect=[pr, {'permission': permission}, [{'changes': 0}]])
                if permission in {'admin', 'write'}:
                    ai_review.collect(github, 46, 'team/repo', 'abc')
                    self.assertEqual(github.call_count, 3)
                else:
                    with self.assertRaisesRegex(ValueError, 'write access'):
                        ai_review.collect(github, 46, 'team/repo', 'abc')
                    self.assertEqual(github.call_count, 2)
                self.assertEqual(github.call_args_list[1].args,
                                 ('/collaborators/teammate/permission',))

    def test_unexpected_eligibility_failure_is_not_a_successful_skip(self):
        import io
        import json
        import os
        import runpy
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory, 'event.json')
            summary = Path(directory, 'summary.md')
            event.write_text(json.dumps({'number': 44, 'pull_request': {'head': {'sha': 'abc'}}}))
            pr = dict(self.fixture(), author_association='CONTRIBUTOR')
            with patch.dict(os.environ, GITHUB_REPOSITORY='team/repo', GH_TOKEN='github',
                            OPENAI_API_KEY='openai', GITHUB_EVENT_PATH=str(event),
                            GITHUB_STEP_SUMMARY=str(summary)), \
                    patch('urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(pr).encode()),
                          io.BytesIO(b'{"permission":"read"}')]) as request, \
                    patch('builtins.print'), self.assertRaises(SystemExit) as result:
                runpy.run_path(ai_review.__file__, run_name='__main__')
            self.assertEqual(result.exception.code, 1)
            self.assertEqual(request.call_count, 2)
            self.assertIn('PR author must have repository write access', summary.read_text())

    def test_collect_related_gherkin_and_patch(self):
        github = Mock(side_effect=[self.fixture(), {'permission': 'write'}, [{'filename': 'a.py', 'changes': 1,
                       'patch': '+code', 'status': 'added'}],
                       {'title': 'Story', 'body': 'Scenario: Valid input'}])
        result = ai_review.collect(github, 40, 'team/repo', 'abc')
        self.assertEqual(result['issues'][0]['body'], 'Scenario: Valid input')
        self.assertEqual(result['changes'][0]['patch'], '+code')

    def test_collect_rejects_stale_closed_oversize_and_missing_patch(self):
        pr = self.fixture()
        for responses, sha in (([pr], 'old'), ([dict(pr, state='closed')], 'abc'),
                               ([pr, {'permission': 'write'}, []], 'abc'),
                               ([pr, {'permission': 'write'}, [{'changes': 1}]], 'abc')):
            with self.subTest(responses=responses), self.assertRaises(ValueError):
                ai_review.collect(Mock(side_effect=responses), 40, 'team/repo', sha)

    def test_pr_references_are_not_treated_as_story_issues(self):
        github = Mock(side_effect=[self.fixture(), {'permission': 'write'}, [{'changes': 0}], {'pull_request': {}}])
        self.assertEqual(ai_review.collect(github, 40, 'team/repo', 'abc')['issues'], [])

    def test_successful_request_parses_json(self):
        import io
        with patch('scripts.ai_review.urlopen', return_value=io.BytesIO(b'{"ok":true}')) as open_url:
            self.assertEqual(ai_review.request_json('https://api.github.com/test', 'token'), {'ok': True})
        self.assertEqual(open_url.call_args.args[0].get_method(), 'GET')

    def test_network_failure_is_sanitized(self):
        from urllib.error import URLError
        for failure in (URLError('private'), TimeoutError('private')):
            with self.subTest(failure=failure), patch('scripts.ai_review.urlopen', side_effect=failure):
                with self.assertRaisesRegex(RuntimeError, 'POST to api.openai.com.*timed out') as error:
                    ai_review.request_json('https://api.openai.com/v1/responses', 'secret', {})
                self.assertNotIn('private', str(error.exception))
                self.assertNotIn('secret', str(error.exception))

    def test_invalid_api_json_identifies_service_without_exposing_body(self):
        import io
        with patch('scripts.ai_review.urlopen', return_value=io.BytesIO(b'private response')):
            with self.assertRaisesRegex(RuntimeError, 'Invalid JSON.*GET to api.github.com') as error:
                ai_review.request_json('https://api.github.com/test', 'secret')
        self.assertNotIn('private', str(error.exception))
        self.assertNotIn('secret', str(error.exception))

    def test_main_connects_collection_review_and_publication(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory, 'event.json')
            event.write_text(json.dumps({'number': 40, 'pull_request': {'head': {'sha': 'abc'}}}))
            replies = [dict(self.fixture(), body=''), {'permission': 'write'}, [{'changes': 0}],
                       {'status': 'completed', 'output': [{'type': 'message', 'content': [
                           {'type': 'output_text', 'text': 'No supported findings.'}]}]},
                       self.fixture(), {}]
            with patch.dict(os.environ, GITHUB_REPOSITORY='team/repo', GH_TOKEN='github',
                            OPENAI_API_KEY='openai', GITHUB_EVENT_PATH=str(event)), \
                    patch.object(ai_review, 'request_json', side_effect=replies) as request, \
                    patch('builtins.print') as log:
                ai_review.main()
                self.assertEqual(request.call_count, 6)
                self.assertEqual(request.call_args.args[0],
                                 'https://api.github.com/repos/team/repo/issues/40/comments')
                messages = [call.args[0] for call in log.call_args_list]
                self.assertIn('Collecting PR #40 at abc', messages)
                self.assertIn('Generating review with gpt-6-luna', messages)
                self.assertIn('Publishing review for PR #40', messages)
            with patch.dict(os.environ, GITHUB_REPOSITORY='team/repo', GH_TOKEN='github',
                            OPENAI_API_KEY=''), self.assertRaisesRegex(ValueError, 'missing'):
                ai_review.main()

    def test_line_gate_uses_exact_threshold_not_combined_or_rounded_score(self):
        import json
        for covered, total, expected in ((80, 100, True), (79, 100, False),
                                         (7999, 10000, False), (0, 0, False)):
            report = json.dumps({'totals': {'covered_lines': covered, 'num_statements': total}})
            with patch.object(Path, 'read_text', return_value=report), patch('builtins.print'):
                self.assertEqual(check_coverage.check(), expected)

    def test_issue_links_are_same_repository_and_deduplicated(self):
        body = ('Closes #12. Related issues: #13 #12 '
                'https://github.com/team/repo/issues/14 '
                'https://github.com/other/repo/issues/15 other/repo#16')
        self.assertEqual(ai_review.issue_numbers(body, 'team/repo'), [12, 13, 14])

    def test_issue_context_is_bounded(self):
        with self.assertRaisesRegex(ValueError, 'issues'):
            ai_review.issue_numbers(' '.join(f'#{i}' for i in range(1, 8)), 'team/repo')

    def test_review_uses_only_luna_and_one_bounded_request(self):
        api = Mock(return_value={'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Finding'}]}]})
        self.assertEqual(ai_review.review({'diff': 'example'}, api), 'Finding')
        payload = api.call_args.args[0]
        self.assertEqual(payload['model'], 'gpt-6-luna')
        self.assertFalse(payload['store'])
        self.assertNotIn('tools', payload)
        self.assertEqual(api.call_count, 1)

    def test_oversize_input_never_calls_api(self):
        api = Mock()
        with self.assertRaisesRegex(ValueError, 'large'):
            ai_review.review({'diff': 'x' * 130_000}, api)
        api.assert_not_called()

    def test_incomplete_empty_and_refused_results_fail(self):
        for result in ({'status': 'incomplete'}, {'status': 'completed', 'output': []},
                       {'status': 'completed', 'output': [{'type': 'message', 'content':
                        [{'type': 'refusal', 'refusal': 'No'}]}]}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                ai_review.review({}, Mock(return_value=result))

    def test_output_limit_failure_explains_incomplete_review(self):
        result = {'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}}
        with self.assertRaisesRegex(ValueError, 'output token limit'):
            ai_review.review({}, Mock(return_value=result))

    def test_stale_head_does_not_publish(self):
        github = Mock(return_value={'head': {'sha': 'new'}})
        with self.assertRaisesRegex(ValueError, 'changed'):
            ai_review.publish(github, 40, 'old', 'review')
        self.assertEqual(github.call_count, 1)

    def test_comment_identifies_reviewed_commit(self):
        github = Mock(return_value={'head': {'sha': 'abc'}})
        ai_review.publish(github, 40, 'abc', 'Finding')
        body = github.call_args.kwargs['data']['body']
        self.assertIn('abc', body)
        self.assertIn('Finding', body)
        self.assertIn('advisory', body)

    def test_api_errors_do_not_expose_response_or_credentials(self):
        import io
        from urllib.error import HTTPError
        for host, status, headers, expected_id in (
                ('api.openai.com', 429, {'x-request-id': 'req_123'}, 'req_123'),
                ('api.github.com', 403, {'x-github-request-id': '123:ABC'}, '123:ABC'),
                ('api.github.com', 500, {}, 'unavailable'),
                ('api.github.com', 403, {'x-github-request-id': 'private\nforged log'}, 'unavailable')):
            with self.subTest(host=host, status=status), patch('scripts.ai_review.urlopen',
                    side_effect=HTTPError(f'https://{host}/test', status, 'private error',
                                          headers, io.BytesIO(b'private response'))):
                with self.assertRaisesRegex(RuntimeError, f'HTTP {status} during POST to {host}') as error:
                    ai_review.request_json(f'https://{host}/test', 'secret', {})
            self.assertIn(expected_id, str(error.exception))
            self.assertNotIn('private', str(error.exception))
            self.assertNotIn('secret', str(error.exception))
