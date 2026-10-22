# Implementation record

Use this shared record for PR review, sprint reports, and demo preparation. Add
newest entries first, one per logical commit or PR; group related small changes.
Explain the combined result, regardless of who wrote it. AI attribution belongs
in the README's AI usage log. Link to source and existing specifications instead
of copying them. Do not reconstruct undocumented historical decisions.

## Entry format

Use a dated heading and a few short bullets: issue/PR reference, what changed
and why, and important behavior limits. Link to source or acceptance scenarios.
Keep validation results and execution history out of this record.

## Changes

### 2026-10-22 — Show account form submission progress

- [#10](https://github.com/CS4300-CS5300-FA26/team-3/issues/10) and
  [#11](https://github.com/CS4300-CS5300-FA26/team-3/issues/11); PR pending.
  [Account forms](../src/accounts/templates/accounts/base.html) show progress and
  prevent repeat submissions while waiting. Restore controls on browser Back;
  [email failures](../features/signup.feature) leave signup ready to retry.
  Email sending still completes before the confirmation redirect.

### 2026-10-22 — Identify the deployment health probe

- Deployment follow-up; PR pending. Give the public health probe a BudgetWise
  user agent so Cloudflare does not reject Python's default client signature.
  Report the actual failing HTTP status and retain automatic rollback.

### 2026-10-22 — Match dashboard styling to the account pages

- **Reference:** [#11](https://github.com/CS4300-CS5300-FA26/team-3/issues/11)
  and [#21](https://github.com/CS4300-CS5300-FA26/team-3/issues/21); PR pending.
- Reuse the shared account layout and navigation on the dashboard. Style the
  month summary and transaction list for desktop and narrow screens, removing
  the duplicate navigation and sign-out form.

### 2026-10-22 — Complete signup and connect account navigation

- **Reference:** [#10](https://github.com/CS4300-CS5300-FA26/team-3/issues/10),
  integrated with [#11](https://github.com/CS4300-CS5300-FA26/team-3/issues/11);
  [PR #55](https://github.com/CS4300-CS5300-FA26/team-3/pull/55).
- Add [email-only signup](../src/accounts/signup.py), 24-hour single-use verification,
  password setup, and existing-account notices with identical public confirmations.
  Shared database limits bound email delivery; application logs redact tokens.
- Connect signup, sign-in, dashboard, income, expense, and POST sign-out through
  shared navigation. Require sign-in for application URLs except signup and keep
  Django admin login separate. Use the private dashboard provided by D2 (#53).
  See the [signup journey](../features/signup.feature).
- Merge the independent signup and sign-in migrations without rewriting their history.
  Real mail requires configured Resend credentials. The deployment candidate probe
  checks the public sign-in page because the homepage now redirects anonymous users.

### 2026-10-22 — Complete sign-in and the personal budget dashboard

- **Reference:** [PR #53](https://github.com/CS4300-CS5300-FA26/team-3/pull/53),
  [#11](https://github.com/CS4300-CS5300-FA26/team-3/issues/11), and
  [#21](https://github.com/CS4300-CS5300-FA26/team-3/issues/21).
- Add email sign-in, POST sign-out, and a 15-minute lockout after five failures.
  Serialize sign-in decisions; allow 10 attempts per source IP and 100 overall
  per minute using expiring hashed counters in one shared row. Shared networks
  share their source allowance. Prune expired records on the first sign-in each minute.
- Serve the user's monthly transactions and remaining budget at `/` and
  `/dashboard/`, with private cache headers. Remove `/demo/`; retained synthetic
  rows stay excluded. Connect income, expense, and sign-out.
- Exercise real user-owned data in the [D6 scenarios](../features/remaining_budget.feature)
  and enable the income/expense success scenarios. See the
  [sign-in scenarios](../features/sign_in_lockout.feature) and
  [lockout implementation](../src/accounts/lockout.py).
- Probe the public sign-in page before deployment promotion, since anonymous
  requests to `/` now redirect.

### 2026-10-21 — Assign new transactions to students

- **Reference:** [Issue #12](https://github.com/CS4300-CS5300-FA26/team-3/issues/12) and [Issue #18](https://github.com/CS4300-CS5300-FA26/team-3/issues/18); [PR #52](https://github.com/CS4300-CS5300-FA26/team-3/pull/52).
- The [income and expense save paths](../src/transactions/views.py) now assign the signed-in student to each new transaction before saving it. The [income](../tests/test_transaction_view.py) and [expense](../tests/test_expense_view.py) view tests check that ownership.
- Existing and demo transactions may have no owner; the D2 dashboard excludes them.

### 2026-10-21 — Income/expense success scenarios and shared Behave steps

- **Reference:** [#12](https://github.com/CS4300-CS5300-FA26/team-3/issues/12) and
  [#18](https://github.com/CS4300-CS5300-FA26/team-3/issues/18); [PR #51](https://github.com/CS4300-CS5300-FA26/team-3/pull/51).
- Add "Paycheck is recorded" and "Fixed expense is recorded", worded as in the
  issues, to the [income](../features/record_income.feature) and
  [expense](../features/record_expense.feature) features, with steps that check
  the dashboard list and remaining budget for the new entry.
- Move the sign-in setup and shared checks into
  [common_steps.py](../features/steps/common_steps.py), so the income and expense
  steps no longer import each other. All four scenarios now start with the issues'
  wording, `Given I am signed in`.
- Initially pending D2; both scenarios are now enabled against the private dashboard.

### 2026-10-19 — Record an expense (D-4)

- **Reference:** [Issue #18](https://github.com/CS4300-CS5300-FA26/team-3/issues/18); PR pending.
- Add a signed-in-only [expense page](../src/transactions/templates/transactions/record_expense.html)
  at `/expense/` with amount, date, description, a required category (Housing,
  Food, Books, Transportation, or Other), and a Fixed/Variable choice, so rent
  can be told apart from coffee. Descriptions made only of invisible characters,
  such as a zero-width space, are rejected. See the [acceptance scenario](../features/record_expense.feature).
- Student ownership and dashboard integration were added in the entries above.

### 2026-10-19 — Calendar month budget summary

- **Reference:** [Issue #21](https://github.com/CS4300-CS5300-FA26/team-3/issues/21); [PR #48](https://github.com/CS4300-CS5300-FA26/team-3/pull/48).
- Add a month selector and exact income-minus-expenses total to the
  initial demo dashboard, with current-month fallback and
  an empty-period message. See the [acceptance scenarios](../features/remaining_budget.feature).
- Add a repeatable [demo command](../src/transactions/management/commands/seed_demo_transactions.py)
  for January 2027 examples, preserving existing records.
- The later D2 integration applies this behavior to user-owned transactions.

### 2026-10-18 — Shared account foundation

- **Reference:** [Issue #10](https://github.com/CS4300-CS5300-FA26/team-3/issues/10).
- Add [shared identity helpers](../src/accounts/identity.py) for canonical email and
  ordinary Django user creation after mailbox verification, supported by
  [foundation scenarios](../features/account_identity.feature).
- Enforce nonempty email uniqueness in the database across usernames, ignoring
  ASCII case, surrounding spaces, and a trailing domain dot. Store international
  domains as punycode;
  direct database writes must use printable ASCII. Empty emails remain allowed.
- Callers must verify mailbox ownership before creating an account.

### 2026-10-17 — Record income regression coverage and page feedback

- **Reference:** [Issue #12](https://github.com/CS4300-CS5300-FA26/team-3/issues/12); follow-up PR pending.
- Add [view regression tests](../tests/test_transaction_view.py) for access, CSRF,
  negative amounts, and posted field overrides, plus a [Behave scenario](../features/record_income.feature)
  for the non-positive amount criterion.
- Show source errors and save confirmation on the [income page](../src/transactions/templates/transactions/record_income.html),
  with clearer styling and a BudgetWise home link.
- Student ownership and dashboard integration were added in the entries above.

### 2026-10-17 — Fix unexpected AI-review skips

- **Reference:** #41; prompted by PR #44, delivery pending.
- Check author/repository eligibility in the [review script](../.github/scripts/ai_review.py)
  using current GitHub metadata; report failures in the Actions summary. Drafts
  still skip normally. Takes effect after human delivery to `main`.

### 2026-10-12 — Luna PR review and CI coverage

- **Reference:** [Issue #41](https://github.com/CS4300-CS5300-FA26/team-3/issues/41),
  Sprint 1; commit/PR pending.
- **Changes:** Luna reviews PR patches and referenced issue criteria using trusted
  base-branch code. CI runs Django and Behave tests, reports coverage, and enforces
  80% line coverage. See the [review script](../.github/scripts/ai_review.py),
  [CI workflow](../.github/workflows/ci.yml), and [scenarios](../features/ai_review.feature).
- **Limits:** Reviews activate once the workflow reaches `main`. Feedback is
  advisory and limited to patches and linked issues.

### 2026-10-08 — Sprint 1 development guidance

- **Reference / requirement:** Pending commit; requested team-wide guidance for
  simple, explainable code, SOLID, TDD, coverage, and consolidated explanations.
- **Result and design:** [AGENTS.md](../AGENTS.md) routes agents to relevant files
  and defines RED–GREEN–REFACTOR, practical SOLID boundaries, coverage reporting,
  and teammate walkthroughs. This record holds unified implementation explanations;
  README retains AI attribution. Existing tagged-demo review guidance is condensed.
- **Limits:** Instructions guide future work; they do not install coverage tooling,
  enforce a CI coverage gate, or establish teammate understanding. No application
  behavior changes.
