# Implementation record

Use this shared record for PR review, sprint reports, and demo preparation. Add
newest entries first, one per logical commit or PR; group related small changes.
Explain the combined result, regardless of who wrote it. AI attribution belongs
in the README's AI usage log. Link to source and existing specifications instead
of copying them. Do not reconstruct undocumented historical decisions.

## Entry format

### Date — Change title

- **Reference / requirement:** Commit or PR (pending until available), issue/story
  or requested behavior; sprint when known.
- **Result and flow:** What changed and how the user action travels through the
  affected components to its result. Include relevant file/symbol links.
- **Design:** Significant choices, rationale, and useful alternatives/tradeoffs.
- **Failures and limits:** Validation, abuse/failure handling, known gaps, and
  unresolved decisions relevant to this change.
- **Verification:** Actual commands/results, RED–GREEN evidence, coverage scope
  and gaps, or why a check does not apply. Never imply an unperformed check passed.
- **Demo / review:** A short example and likely questions with supported answers
  for substantial changes. Tagged demo reviews also record the exact remote SHA,
  prioritized questions/follow-ups, SHA-bound code references, and proposed fixes.

Omit inapplicable fields for small edits. Keep pending entries current before
handoff; preserve historical results and record later behavior in a new entry.

## Changes

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
- **Verification:** Documentation-only review; `git diff --check` passed. Application
  tests and coverage do not apply to this change.
