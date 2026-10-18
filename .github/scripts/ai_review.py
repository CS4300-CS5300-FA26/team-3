"""Bounded, advisory PR review. PR content is data, never executable code."""
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = 'gpt-6-luna'
MAX_INPUT_BYTES = 120_000


def request_json(url, token, data=None):
    request = Request(url, data=None if data is None else json.dumps(data).encode(),
                      headers={'Authorization': f'Bearer {token}',
                               'Accept': 'application/vnd.github+json' if url.startswith(
                                   'https://api.github.com/') else 'application/json',
                               'Content-Type': 'application/json'})
    operation = f'{request.get_method()} to {request.host}'
    try:
        # No automatic retries: a timed-out generation may still incur a charge.
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        request_id = error.headers.get('x-request-id') or error.headers.get('x-github-request-id', 'unavailable')
        if not re.fullmatch(r'[A-Za-z0-9_:-]{1,128}', request_id):
            request_id = 'unavailable'
        raise RuntimeError(f'API request failed: HTTP {error.code} during {operation}; '
                           f'request ID: {request_id}') from None
    except (URLError, TimeoutError):
        raise RuntimeError(f'{operation} failed or timed out; inspect service status before rerunning') from None
    except json.JSONDecodeError:
        raise RuntimeError(f'Invalid JSON response during {operation}') from None


def issue_numbers(body, repository):
    """Explicit local #N references and same-repository issue URLs only."""
    urls = re.findall(r'https://github\.com/([^\s/]+/[^\s/]+)/issues/(\d+)', body)
    without_urls = re.sub(r'https?://\S+', '', body)
    numbers = [int(n) for n in re.findall(r'(?<![\w/])#(\d+)\b', without_urls)]
    numbers += [int(n) for repo, n in urls if repo.lower() == repository.lower()]
    result = sorted(set(numbers))
    if len(result) > 6:
        raise ValueError('Too many related issues; limit explicit references to six')
    return result


def collect(github, number, repository, expected_sha):
    pr = github(f'/pulls/{number}')
    if pr['head']['sha'] != expected_sha or pr['state'] != 'open':
        raise ValueError('PR changed or closed; use its latest review run')
    # Read trust metadata from GitHub, not optional event-time author fields.
    if pr['draft'] is not False or pr['base']['ref'] != 'main':
        raise ValueError('PR must be non-draft and target main')
    if (pr['head']['repo'] or {}).get('full_name', '').lower() != repository.lower():
        raise ValueError('PR head is not in this repository')
    if pr['author_association'] not in {'OWNER', 'MEMBER', 'COLLABORATOR'}:
        raise ValueError('PR author is not an owner, member, or collaborator')
    files = github(f'/pulls/{number}/files?per_page=100')
    if len(files) != pr['changed_files'] or len(files) > 60:
        raise ValueError('PR too large for one review; split it into smaller PRs')
    changes = []
    for file in files:
        if not file.get('patch') and file['changes']:
            raise ValueError('A changed file has no reviewable patch; manual review required')
        changes.append({key: file.get(key) for key in
                        ('filename', 'previous_filename', 'status', 'patch')})
    issues = []
    for issue in issue_numbers(pr.get('body') or '', repository):
        value = github(f'/issues/{issue}')
        if 'pull_request' not in value:
            issues.append({'number': issue, 'title': value['title'], 'body': value['body']})
    return {'title': pr['title'], 'description': pr.get('body'),
            'base_sha': pr['base']['sha'], 'head_sha': expected_sha,
            'issues': issues, 'changes': changes}


def review(context, api):
    prompt = Path(__file__).with_name('review_prompt.md').read_text()
    content = json.dumps(context, ensure_ascii=True)
    if len((prompt + content).encode()) > MAX_INPUT_BYTES:
        raise ValueError('Review input too large; split the PR instead of silently truncating it')
    result = api({'model': MODEL, 'instructions': prompt, 'input': content,
                  'reasoning': {'effort': 'medium'}, 'max_output_tokens': 6000, 'store': False})
    if result.get('status') != 'completed':
        if (result.get('incomplete_details') or {}).get('reason') == 'max_output_tokens':
            raise ValueError('OpenAI review reached its output token limit; no partial review was posted')
        raise ValueError('OpenAI review did not complete; this is not a clean review')
    parts = [part for item in result.get('output', []) if item.get('type') == 'message'
             for part in item.get('content', [])]
    if any(part.get('type') == 'refusal' for part in parts):
        raise ValueError('OpenAI declined the review')
    output = '\n'.join(part['text'] for part in parts if part.get('type') == 'output_text')
    if not output.strip() or len(output) > 50_000:
        raise ValueError('OpenAI returned an empty or oversized review')
    return output


def publish(github, number, sha, output):
    if github(f'/pulls/{number}')['head']['sha'] != sha:
        raise ValueError('PR changed during review; no stale feedback was posted')
    # Commit label remains useful if a push races the final readback.
    body = (f'## Automated Luna review\n\nReviewed commit: `{sha}`\n\n'
            'This is advisory feedback based on the PR diff and explicitly referenced '
            'issue bodies. It does not execute tests or prove security or coverage. '
            'Consult the separate CI coverage report.\n\n' + output)
    github(f'/issues/{number}/comments', data={'body': body})


def main():
    repository = os.environ['GITHUB_REPOSITORY']
    github_token = os.environ['GH_TOKEN']
    api_key = os.environ['OPENAI_API_KEY']
    if not api_key:
        raise ValueError('OPENAI_API_KEY is missing')
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    number = int(event['number'])
    sha = event['pull_request']['head']['sha']

    def github(path, data=None):
        return request_json(f'https://api.github.com/repos/{repository}{path}', github_token, data)

    print(f'Collecting PR #{number} at {sha}', flush=True)
    context = collect(github, number, repository, sha)
    print(f'Generating review with {MODEL}', flush=True)
    output = review(context, lambda data: request_json(
        'https://api.openai.com/v1/responses', api_key, data))
    print(f'Publishing review for PR #{number}', flush=True)
    publish(github, number, sha, output)
    print(f'Posted advisory review for PR #{number} at {sha}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError) as error:
        # Never print API response bodies, request headers, or credentials.
        message = f'Review failed: {error}'
        print(message)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
                summary.write(message + '\n')
        raise SystemExit(1)
