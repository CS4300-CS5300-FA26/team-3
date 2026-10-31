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

### 2026-10-30 — Complete transaction editing and deletion from the dashboard

- [#19](https://github.com/CS4300-CS5300-FA26/team-3/issues/19); merged through
  [#62](https://github.com/CS4300-CS5300-FA26/team-3/pull/62) (editing),
  [#63](https://github.com/CS4300-CS5300-FA26/team-3/pull/63) (deletion), and
  [#67](https://github.com/CS4300-CS5300-FA26/team-3/pull/67) (dashboard actions
  and acceptance scenarios). [Transaction views](../src/transactions/views.py)
  reuse the recording forms, require the signed-in owner, and exclude demo rows.
- Deletion needs a confirmation POST; cancelling preserves the record. Saved
  changes affect the monthly budget, and successful actions return to the current
  month's dashboard. [Scenarios](../features/transaction_management.feature)
  cover editing, deletion, cancellation, ownership, and dashboard links.

### 2026-10-30 — Warn below the saved safety threshold

- [#22](https://github.com/CS4300-CS5300-FA26/team-3/issues/22);
  merged in [#66](https://github.com/CS4300-CS5300-FA26/team-3/pull/66).
  The [dashboard](../src/accounts/views.py) compares the selected month's
  remaining budget with the signed-in student's saved threshold and shows the
  specified warning only when it is lower. The
  [acceptance scenarios](../features/low_balance_warning.feature) cover the
  warning at $120 and its absence at $310 for a $150 threshold.
- Equality and an unset threshold do not warn. An empty month has zero balance
  and warns when the threshold is positive. The warning stays inline below the
  threshold editor; it does not send notifications or add a new migration.

### 2026-10-29 — Add password-reset email requests and throttling

- [#23](https://github.com/CS4300-CS5300-FA26/team-3/issues/23); pending PR #68.
  [Reset requests](../src/accounts/password_reset_requests.py) admit at most five
  requests per normalized email in a rolling hour, including unknown addresses
  and failed deliveries. Store only a hashed address and bounded timestamps;
  requesting mail does not change passwords, sessions or sign-in lockout.
- Share the [account mail helper](../src/accounts/mail.py) and email style with
  signup. Eligible accounts receive Django's 30-minute reset tokens; all expected
  outcomes return the same confirmation. Synchronous delivery still differs in timing.
  [Service scenarios](../features/password_reset_requests.feature) use a test-only
  route. Public pages follow separately: mail remains disabled until
  `accounts:reset_password` resolves with `uidb64` and `token`. The future
  completion view must call the reset core.
- Extend [application-log redaction](../src/accounts/logging.py) to Django reset
  tokens so request logs do not expose recovery credentials.

### 2026-10-29 — Align linting with Sprint 3

- Follow-up to [#41](https://github.com/CS4300-CS5300-FA26/team-3/issues/41)
  in merged [PR #65](https://github.com/CS4300-CS5300-FA26/team-3/pull/65).
  Use Flake8 as our single linter, as allowed by the Sprint 3 rubric, with console
  reports and the existing [failure scenarios](../features/ci_quality.feature).
  Preserve the focused rule scope in [.flake8](../.flake8) and remove the old
  linter dependency/configuration; intentional bootstrap imports remain allowed.

### 2026-10-29 — Address Sprint 1 CI feedback

- Follow-up to [#41](https://github.com/CS4300-CS5300-FA26/team-3/issues/41);
  merged in [#65](https://github.com/CS4300-CS5300-FA26/team-3/pull/65).
  [CI](../.github/workflows/ci.yml) checks every branch push, retains
  PR checks, and adds lint and dependency auditing to the test job.
  A weekly run and [review cadence](../README.md#tests-and-automated-review) catch
  new advisories; [lint scenarios](../features/ci_quality.feature) cover failures.
- Update certifi to 2026.10.19 for
  [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2).
  Full formatting, type checking, and live service alerts remain outside this change.

### 2026-10-28 — Add the password-reset core

- [#23](https://github.com/CS4300-CS5300-FA26/team-3/issues/23);
  merged in [#64](https://github.com/CS4300-CS5300-FA26/team-3/pull/64).
  [Reset completion](../src/accounts/password_reset.py) uses Django's 30-minute
  tokens and password validation, replaces the password and clears sign-in lockout
  atomically, and invalidates existing sessions and outstanding tokens.
  [Core scenarios](../features/password_reset_core.feature) cover recovery and
  expiry. Email requests and throttling are covered by pending PR #68, recorded
  above; public reset pages follow separately.

### 2026-10-27 — Store and set safety thresholds

- [#22](https://github.com/CS4300-CS5300-FA26/team-3/issues/22);
  merged in [#61](https://github.com/CS4300-CS5300-FA26/team-3/pull/61).
  Add an optional [per-student threshold](../src/accounts/models.py) stored in
  exact cents with a nonnegative database constraint. The
  [dashboard](../src/accounts/templates/accounts/dashboard.html) shows the saved
  amount or “Not set” below the monthly balance and lets the signed-in student
  set or change it. [Saving](../src/accounts/views.py) handles competing
  first-time requests without creating a second row. Low-balance warnings
  were subsequently added in #66, recorded above.

### 2026-10-22 — Show account form submission progress

- [#10](https://github.com/CS4300-CS5300-FA26/team-3/issues/10) and
  [#11](https://github.com/CS4300-CS5300-FA26/team-3/issues/11);
  merged in [#59](https://github.com/CS4300-CS5300-FA26/team-3/pull/59).
  [Account forms](../src/accounts/templates/accounts/base.html) show progress and
  prevent repeat submissions while waiting. Restore controls on browser Back;
  [email failures](../features/signup.feature) leave signup ready to retry.
  Email sending still completes before the confirmation redirect.

### 2026-10-22 — Identify the deployment health probe

- Deployment follow-up, merged in
  [#58](https://github.com/CS4300-CS5300-FA26/team-3/pull/58). Give the public health probe a BudgetWise
  user agent so Cloudflare does not reject Python's default client signature.
  Report the actual failing HTTP status and retain automatic rollback.

### 2026-10-22 — Match dashboard styling to the account pages

- **Reference:** [#11](https://github.com/CS4300-CS5300-FA26/team-3/issues/11)
  and [#21](https://github.com/CS4300-CS5300-FA26/team-3/issues/21);
  merged in [#57](https://github.com/CS4300-CS5300-FA26/team-3/pull/57).
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
- Both scenarios are enabled against the private dashboard added in #53.

### 2026-10-19 — Record an expense (D-4)

- **Reference:** [Issue #18](https://github.com/CS4300-CS5300-FA26/team-3/issues/18);
  merged in [PR #50](https://github.com/CS4300-CS5300-FA26/team-3/pull/50).
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

- **Reference:** [Issue #12](https://github.com/CS4300-CS5300-FA26/team-3/issues/12);
  merged in [PR #47](https://github.com/CS4300-CS5300-FA26/team-3/pull/47), following #44.
- Add [view regression tests](../tests/test_transaction_view.py) for access, CSRF,
  negative amounts, and posted field overrides, plus a [Behave scenario](../features/record_income.feature)
  for the non-positive amount criterion.
- Show source errors and save confirmation on the [income page](../src/transactions/templates/transactions/record_income.html),
  with clearer styling and a BudgetWise home link.
- Student ownership and dashboard integration were added in the entries above.

### 2026-10-17 — Fix unexpected AI-review skips

- **Reference:** [#41](https://github.com/CS4300-CS5300-FA26/team-3/issues/41),
  prompted by #44; merged in [#45](https://github.com/CS4300-CS5300-FA26/team-3/pull/45).
- Check author/repository eligibility in the [review script](../.github/scripts/ai_review.py)
  using current GitHub metadata; report failures in the Actions summary. Drafts
  still skip normally. [#46](https://github.com/CS4300-CS5300-FA26/team-3/pull/46)
  subsequently added comment permissions, safe failure diagnostics, and the
  repository-permission check now used for reviewer eligibility.

### 2026-10-12 — Luna PR review and CI coverage

- **Reference:** [Issue #41](https://github.com/CS4300-CS5300-FA26/team-3/issues/41),
  Sprint 1; merged in [PR #42](https://github.com/CS4300-CS5300-FA26/team-3/pull/42).
- **Changes:** Luna reviews PR patches and referenced issue criteria using trusted
  base-branch code. CI runs Django and Behave tests, reports coverage, and enforces
  80% line coverage. See the [review script](../.github/scripts/ai_review.py),
  [CI workflow](../.github/workflows/ci.yml), and [scenarios](../features/ai_review.feature).
- **Limits:** The workflow is on `main`; review execution still requires its
  configured API secret and an eligible PR event. Feedback is advisory and
  limited to patches and linked issues.

### 2026-10-08 — Sprint 1 development guidance

- **Reference / requirement:** Commit
  [fa13615](https://github.com/CS4300-CS5300-FA26/team-3/commit/fa13615);
  requested team-wide guidance for
  simple, explainable code, SOLID, TDD, coverage, and consolidated explanations.
- **Result and design:** [AGENTS.md](../AGENTS.md) routes agents to relevant files
  and defines RED–GREEN–REFACTOR, practical SOLID boundaries, coverage reporting,
  and teammate walkthroughs. This record holds unified implementation explanations;
  README retains AI attribution. Existing tagged-demo review guidance is condensed.
- **Limits:** These instructions do not establish teammate understanding or change
  application behavior. Coverage tooling and the CI gate were added separately
  in #42; this entry records the original guidance change.
