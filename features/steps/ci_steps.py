"""Issue #41 acceptance checks with fake external services."""
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch

from behave import given, when, then

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github"))
from scripts import ai_review, check_coverage


@given('a pull request references an issue with Gherkin acceptance criteria')
def related_issue(context):
    context.pr = {'head': {'sha': 'abc', 'repo': {'full_name': 'team/repo'}},
                  'base': {'sha': 'base', 'ref': 'main'}, 'state': 'open',
                  'draft': False, 'user': {'login': 'teammate'},
                  'changed_files': 1, 'title': 'Validate input', 'body': 'Closes #12'}
    context.github = Mock(side_effect=[context.pr, {'permission': 'write'},
        [{'filename': 'src/example.py', 'changes': 1, 'patch': '+validate(input)'}],
        {'title': 'Validation', 'body': 'Scenario: Invalid input is rejected'}, context.pr, {}])
    context.api = Mock(return_value={'status': 'completed', 'output': [
        {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Add invalid-input tests.'}]}]})


def run_review(context):
    try:
        data = ai_review.collect(context.github, 41, 'team/repo', 'abc')
        output = ai_review.review(data, context.api)
        ai_review.publish(context.github, 41, 'abc', output)
        context.error = None
    except (RuntimeError, ValueError) as error:
        context.error = error


@when('the automated review completes')
def complete(context):
    run_review(context)
    assert context.error is None


@then('the model receives the scenario and proposed changes')
def scenario_received(context):
    data = json.loads(context.api.call_args.args[0]['input'])
    assert data['issues'][0]['body'] == 'Scenario: Invalid input is rejected'
    assert data['changes'][0]['patch'] == '+validate(input)'


@then('feedback identifying the reviewed commit is posted')
def posted(context):
    assert context.github.call_args.args[0] == '/issues/41/comments'
    assert '`abc`' in context.github.call_args.kwargs['data']['body']


@when('the review API fails')
def api_failure(context):
    context.api.side_effect = RuntimeError('API request failed: HTTP 429')
    run_review(context)


@when('the pull request changes during review')
def stale_review(context):
    def change_head(payload):
        context.pr['head']['sha'] = 'new'
        return context.api.return_value
    context.api.side_effect = change_head
    run_review(context)


@then('the review fails without posting clean feedback')
def no_false_pass(context):
    assert context.error is not None
    assert not any(call.kwargs.get('data') for call in context.github.call_args_list)


@given('measured line coverage is {covered:d} out of 100 lines')
def measured(context, covered):
    context.report = json.dumps({'totals': {'covered_lines': covered, 'num_statements': 100}})


@when('the coverage check runs')
def coverage_gate(context):
    with patch.object(Path, 'read_text', return_value=context.report):
        context.passed = check_coverage.check()


@then('the coverage check {result}')
def coverage_result(context, result):
    assert context.passed == (result == 'passes')


@given('a Python sample with {condition}')
def python_sample(context, condition):
    context.python_source = {
        'valid code': 'value = 1\nprint(value)\n',
        'an undefined name': 'print(missing_value)\n',
        'multiple statements per line': 'value = 1; print(value)\n',
    }[condition]


@when('the CI lint command checks the sample')
def lint_sample(context):
    from tests.test_ci import lint_source

    context.lint_result = lint_source(context.python_source)


@then('the lint check {result}')
def lint_result(context, result):
    assert context.lint_result.returncode == (0 if result == 'passes' else 1), (
        context.lint_result.stdout + context.lint_result.stderr
    )
