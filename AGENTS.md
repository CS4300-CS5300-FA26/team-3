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
├── budgetwise/                   Settings, root URLs, CI settings
│   └── db/aurora/                PostgreSQL IAM connection backend
├── transactions/                 Model/constraints, views, URLs, templates, migrations
├── lambda_entry.py               API Gateway/Lambda request adapter
└── manage.py                     Django command entry point
tests/                            Model/view, host, database, Lambda, deployment tests
.github/workflows/                ci.yml: PostgreSQL checks; cd.yml: deployment
requirements.txt                  Python dependencies
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
- Apply SOLID: give components one cohesive responsibility, extend through clear
  boundaries, preserve contracts when substituting implementations, keep interfaces
  focused on their callers, and isolate external dependencies from domain logic.
  Use functions and Django conventions where sufficient; SOLID does not require
  class hierarchies, service layers, or an interface for every implementation.
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
- Measure line and branch coverage for implementation changes with coverage.py or
  the repository's configured tool. Inspect uncovered changed paths, cover meaningful
  gaps, and report command, scope, result, and justified omissions. Achieve at least
  80% code coverage, as required for Sprint 1; no separate branch-coverage minimum
  is specified. Percentages alone do not prove correctness; never report unmeasured
  coverage as passing or exclude relevant code merely to reach the threshold.
- Document any necessary departure from TDD or unavailable check and its reason.
  Documentation-only changes require full diff review and `git diff --check`, not
  application tests. Keep routine checks local and off AWS to preserve credits.

## Explain and record the work

- Before significant edits, explain intended behavior, affected components, data
  flow, and meaningful tradeoffs in plain language. Give concise checkpoint updates
  and address teammate questions or misunderstandings as work proceeds.
- Finish with the requirement/result, end-to-end flow, design rationale, failure
  handling/limitations, and verification with code pointers. Use a small example
  when helpful. Invite questions without imposing a quiz or routine sign-off;
  delivering an explanation is not evidence that every teammate understands it.
- Maintain `docs/CHANGELOG.md` as the single structured implementation explanation
  record, organized by logical commit or PR. Combine human and agent work into one
  account; keep AI attribution only in README's AI usage log. Give substantial
  features full entries and group minor related edits briefly. Link PR descriptions
  and reports to entries instead of duplicating them in new documents.
- Connect each completed story to its acceptance scenarios, verifying tests, and
  implementation-record entry so reviewers can trace requirements through behavior
  and evidence. Reference existing issue/story identifiers rather than inventing new ones.
- Use the record's entry format, keep pending identifiers explicit, and add real
  commit/PR references when available; never fabricate a SHA or add commits solely
  to record their own hashes. Update setup/operational docs only when made stale.
  Record observed facts separately from intent, inference, and unknowns.
