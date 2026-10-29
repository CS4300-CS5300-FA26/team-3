# AGENTS.md — Team 3 / BudgetWise

CS 4300/5300 Fall 2026 student project. Keep code simple, readable, maintainable,
and consistent so teammates can explain its behavior and defend its tradeoffs.

## Find the relevant context

Read only what the task needs; search symbols and callers before changing code.
Keep this map current when ownership or paths change. Consult the course
[common sprint requirements](https://tghastings.github.io/cs4300andcs5300/common_sprint_requirements.pdf)
when planning, verifying, or preparing sprint deliverables.

```text
README.md                         Setup, sprint plan, AI usage log
docs/
├── BudgetWise Sprint 0-2 Backlog.pdf  Initial requirements/stories/acceptance criteria
├── CHANGELOG.md                   Commit/PR explanations and demo preparation
├── ARCHITECTURE.pdf               Overview; verify against source
└── DEPLOYMENT.md                  Deployment configuration and rollback
src/
├── accounts/                     Signup/mail, identity/verification, D2 sign-in/lockout/budget and private dashboard; D12 password_reset.py core uses Django tokens/forms and clears lockout atomically; default sign-in gate; shared account templates/navigation
├── budgetwise/                   Settings, root URLs, CI settings
│   └── db/aurora/                PostgreSQL IAM connection backend
├── transactions/                 Model/constraints, views, URLs, templates, migrations
├── lambda_entry.py               API Gateway/Lambda request adapter
└── manage.py                     Django command entry point
tests/                            Model/view, host, database, Lambda, deployment tests;
                                  test_accounts.py: identity; test_verification.py: completion; test_password_reset.py: D12 token expiry/password/session/lockout/concurrency; test_registration_view.py: password page; test_signup.py: signup/mail; test_site_flow.py: D1/D2 navigation; test_login_lockout.py: sign-in/budget/cleanup; test_remaining_budget.py: personal budget
                                  test_ci.py: CI triggers and lint failure fixtures
features/                         Behave scenarios tagged with issue numbers;
.github/scripts/                  Luna review/issue context and line-coverage gate
.github/workflows/                ci.yml: all-branch tests/coverage, lint, dependency audit and weekly recheck; ai-review.yml: Luna review;
                                  cd.yml: deployment
requirements.txt                  Python dependencies
requirements-dev.txt              Test/coverage/lint/audit tools; not packaged for Lambda
ruff.toml                         Python lint rules and Lambda bootstrap import exception
```

- Identify the requirement, issue, or acceptance criterion being addressed. Read
  its current details and affected source/tests; the initial backlog and sprint
  plan do not prove a feature is implemented. Never invent identifiers or rules.
- Clarify decisions that materially change behavior or scope; use judgment for
  routine choices and continue independent work. Preserve unrelated local edits.

## Implement simply

- Before any implementation, fetch the latest `origin/main`, verify the development
  branch includes it, and bring the branch up to date if needed. Preserve local work
  and shared history; resolve conflicts before proceeding.
- Humans handle delivery: do not push branches or tags, open or approve PRs, merge
  PRs or changes into `main`, or publish releases. Prepare and verify local changes
  for human handoff. Bringing `origin/main` into the local development branch is
  permitted; it does not authorize remote delivery.
- Reuse the existing Django stack, conventions, and canonical implementations.
  Build only the required behavior and necessary supporting work. Avoid speculative
  features, dependencies, abstractions, and unrelated redesigns.
- Apply SOLID pragmatically: cohesive responsibilities, clear boundaries, preserved
  contracts, focused interfaces, and explicit dependencies. Prefer simple functions
  and Django conventions over unnecessary layers.
- Prefer explicit data flow and straightforward algorithms. Avoid duplication
  without coupling unrelated behavior. Consider query cost and realistic data size.
- Comment non-obvious intent, invariants, ownership boundaries, and failure handling;
  do not narrate syntax. Keep money calculations exact and user data isolated.

## Verify with RED–GREEN–REFACTOR

- For new or changed behavior and bug fixes, first write a focused behavioral test
  and observe it fail for the expected reason (RED). Implement the smallest correct
  change (GREEN), then simplify while keeping tests passing (REFACTOR).
- Express relevant story acceptance criteria as executable Gherkin scenarios using
  Behave, supported by focused unit/integration tests for the underlying logic.
- Test acceptance criteria and relevant failure/abuse paths: invalid input, access
  control, user isolation, duplicates, and external failures. Mock external services
  at their boundaries; avoid tests that merely mirror implementation details.
- Run affected tests while iterating, then applicable CI checks before handoff.
  Local suite: `python src/manage.py test tests src`. For model changes, also run
  `python src/manage.py makemigrations --check --dry-run` and verify migrations.
- Measure line and branch coverage for implementation changes. Require at least
  80% line coverage; no separate branch minimum applies. Inspect uncovered paths
  and report scope, results, and meaningful gaps. Do not exclude code to pass.
- Explain TDD departures or unavailable checks in the handoff.
  Documentation-only changes require full diff review and `git diff --check`, not
  application tests. Keep routine checks local and off AWS to preserve credits.

## Explain and record the work

- Explain significant changes and tradeoffs in plain language. Report checks,
  coverage, and any testing limitations in the handoff, not the changelog.
- Keep `docs/CHANGELOG.md` entries brief: issue/PR reference, what changed and why,
  and important behavior limits. Do not include validation sections, test results,
  coverage numbers, or execution history. Link to source and acceptance scenarios.
- Keep README updates to essential setup and usage. Match the existing AI log
  format: **Tool**, **What it helped with**, and **How we used the result**.
- Avoid duplicating details across documents. Use existing issue identifiers,
  mark pending references honestly, and update docs only when needed.
