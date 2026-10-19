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

### 2026-10-19 — Record an expense (D-4)

- **Reference:** [Issue #18](https://github.com/CS4300-CS5300-FA26/team-3/issues/18); PR pending.
- Add a signed-in-only [expense page](../src/transactions/templates/transactions/record_expense.html)
  at `/expense/` with amount, date, description, a required category (Housing,
  Food, Books, Transportation, or Other), and a Fixed/Variable choice, so rent
  can be told apart from coffee. Descriptions made only of invisible characters,
  such as a zero-width space, are rejected. See the [acceptance scenario](../features/record_expense.feature).
- **Limits:** Expenses are not yet tied to a user, so they do not appear on the
  dashboard or change its remaining budget, which counts demo transactions only (#21).

### 2026-10-19 — Calendar month budget summary

- **Reference:** [Issue #21](https://github.com/CS4300-CS5300-FA26/team-3/issues/21); PR pending.
- Add a month selector and exact income-minus-expenses total to the
  [demo dashboard](../src/transactions/views.py), with current-month fallback and
  an empty-period message. See the [acceptance scenarios](../features/remaining_budget.feature).
- Add a repeatable [demo command](../src/transactions/management/commands/seed_demo_transactions.py)
  for January 2027 examples, preserving existing records.
- **Limits:** Only demo transactions contribute; user-entered income remains
  excluded from the public dashboard.

### 2026-10-17 — Record income regression coverage and page feedback

- **Reference:** [Issue #12](https://github.com/CS4300-CS5300-FA26/team-3/issues/12); follow-up PR pending.
- Add [view regression tests](../tests/test_transaction_view.py) for access, CSRF,
  negative amounts, and posted field overrides, plus a [Behave scenario](../features/record_income.feature)
  for the non-positive amount criterion.
- Show source errors and save confirmation on the [income page](../src/transactions/templates/transactions/record_income.html),
  with clearer styling and a BudgetWise home link.
- **Limits:** Income is not yet associated with a user or reflected in the budget.

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
