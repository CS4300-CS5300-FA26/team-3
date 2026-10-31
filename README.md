# Team 3 - BudgetWise

CS 4300/5300 Fall 2026 — Team 3 group project

> A student-focused budgeting app that helps UCCS students track money in and out, understand what remains, and make more informed spending decisions.

Team Members:

- Fabian Perez Muñoz
- Chase Ripley
- Jack Muterspaugh
- Calvin McDearman
- Noah Dumas

## How to run Django Project locally

Use Python 3.13 (tested locally with Python 3.13.2). The Django project resides in `src/`. Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/manage.py check
python src/manage.py migrate
python src/manage.py runserver 0.0.0.0:3000
```

`check` validates the Django project, and `migrate` creates or updates local SQLite tables. The development server uses port 3000 for DevEdu; open `http://localhost:3000/` for a local setup. Stop it with `Ctrl+C`. The root page requires sign-in and displays the current student's transactions and monthly remaining budget.

Development always accepts `localhost`, `127.0.0.1`, and `[::1]`. Set
`DJANGO_DEVELOPMENT_HOSTS` only if you access the server through another hostname,
using that hostname without a scheme, port, or path (or a comma-separated list).
For example, `export DJANGO_DEVELOPMENT_HOSTS="preview.example.test"` before
starting the server. No extra setting is needed for `localhost:3000`. The Lambda adapter only accepts `budget-wise.dev`
regardless of this environment variable.

For a second DevEdu verification, have a teammate follow the setup above, open
`http://localhost:3000/` (or their configured hostname), and confirm there is no
`DisallowedHost` error. Run
`python src/manage.py test tests.test_hosts tests.test_deployment` as well.
Record the hostname and result when reporting verification.

## Tests and automated review

Install test tools with `python -m pip install -r requirements-dev.txt`.
Run `python src/manage.py test tests src` and `python -m behave` locally.
CI runs on every branch push and PR into `main`, without cancelling earlier
pushes. It requires 80% line coverage and saves coverage reports as artifacts.
The same required `test` check runs `python -m flake8 . --count --statistics`
for Python errors and basic style, plus `python -m pip_audit --strict -r requirements-dev.txt` for
known vulnerabilities in runtime/development dependencies and their transitive
dependencies. Audit failures block the check; JSON reports are retained for 14
days. Flake8 reports violations, counts, and statistics in the CI console to meet
the Sprint 3 linting requirement. Rules live in [.flake8](.flake8); full formatting
and type checking are not enforced.

CI also runs each Monday at 14:17 UTC to catch new dependency advisories. Chase
owns the weekly review using the Actions results and existing GitHub failure
notifications. Triage failures before merging: review the advisory, update the
smallest affected pin, and rerun CI. Any proposed temporary exception needs an
issue recording the advisory ID, reason, owner, and expiry before changing the
audit command; no exceptions are currently configured.

First reviewed audit (2026-10-29, local Python 3.13): the initial audit identified
[GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2) in
certifi 2026.7.22. After updating to 2026.10.19, all 48 resolved dependencies were
audited with no known findings or skipped packages. CI repeats this on Linux.

Luna reviews team PRs using the `OPENAI_API_KEY` GitHub secret. Reference issues
in the PR description (for example, `Related: #12`) to include their Gherkin
criteria.
Drafts skip normally. Other review failures appear in the Actions summary;
current author/repository eligibility is checked using GitHub metadata.

## Create an account (#10)

Open `/accounts/signup/` and enter your email. Follow the single-use link within
24 hours, choose a password, then sign in. Signed-out application visits lead to
sign-in, and successful sign-in resumes supported protected pages.
See [signup email configuration](docs/DEPLOYMENT.md#signup-email) for local links
and the Resend sending credential; automated tests use in-memory email.

## Student sign-in and dashboard (#11, #21)

Sign in with an existing account's email and password at `/sign-in/`. Both `/`
and `/dashboard/` show only that student's transactions and remaining budget for
the selected month. Record income or expenses from the dashboard; sign-out uses
POST and ends the session. The separate `/admin/login/` remains available for
staff accounts, including those without an email.

Incorrect credentials and unknown emails receive the same error. Five failed
sign-ins within 15 minutes lock that email for 15 minutes. A shared database
budget allows 10 sign-in attempts per source IP and 100 overall per minute.
Requests over either limit receive HTTP 429 and can retry after a minute;
source-blocked requests do not consume the overall allowance. Users sharing a
network share its source allowance. Source counters store hashed addresses,
expire with the shared minute window, and ignore client-supplied forwarded headers.

The first sign-in attempt each minute removes expired failure records and idle
email records without clearing active lockouts. No scheduled job is needed.
`python src/manage.py cleanup_login_attempts` remains available for manual cleanup.
PostgreSQL and file-backed SQLite serialize concurrent sign-in decisions;
concurrency tests skip shared in-memory SQLite.

Retained synthetic transactions are excluded from student dashboards. `/demo/`
has been removed; the old seed command is only a development fixture helper.

## Source layout

- `src/budgetwise/`: Django project settings and URLs.
- `src/budgetwise/db/aurora/`: PostgreSQL connection with AWS IAM authentication.
- `src/accounts/`: email identity, sign-in, lockout, and the private dashboard.
- `src/transactions/`: transaction model, recording forms, migrations, and admin registration.
- `src/integrations/`: future Resend, OpenAI, and other service connections.
- `tests/`: transaction, database connection, Lambda, and deployment tests.

## Architecture decisions

Request flow: `Browser → API Gateway → Lambda → Django → Aurora PostgreSQL`

| Choice | Reason |
| --- | --- |
| Django views, templates, and ORM | Keep pages, application logic, and database models in one project that the team can develop together. |
| API Gateway and AWS Lambda | Receive HTTPS requests and run Django without maintaining an application server. Mangum translates requests for Django. |
| Aurora PostgreSQL | Keep deployed data independent of Lambda releases. IAM provides temporary database authentication; separate app and migration users limit who can change the schema. |
| SQLite locally; temporary PostgreSQL in CI | Let teammates develop without AWS accounts and test PostgreSQL compatibility without using Aurora credits. These databases do not share data. |
| Cloudflare DNS and Resend | Cloudflare manages our domain. Django sends signup email through Resend SMTP. |
| GitHub Actions | Test pull requests and automate releases from `main`, using temporary AWS credentials instead of stored access keys. |

## Deployment

Pull requests to `main` run Django checks, migrations, and tests against a temporary PostgreSQL database in GitHub Actions. This uses no AWS credentials or Aurora credits. Teammates can run local tests with `python src/manage.py test tests src`.

Public URL: https://budget-wise.dev/

API Gateway sends requests to Django on AWS Lambda. Anonymous visitors are redirected from `/` to sign-in. The deployment workflow tests changes to `main`, applies migrations, checks the candidate sign-in page, and releases it to Lambda. See [deployment instructions](docs/DEPLOYMENT.md) for configuration and rollback.

## Planned Features (as of Sprint 0-2, subject to change)

- **Account and persistence** — Create an account and securely retain financial records between sessions.
- **Record money in and out** — Add income and expenses so the budget reflects actual cash flow.
- **See where I stand** — View the remaining balance and spending by category.
- **AI-assisted insight** — Receive a short, plain-language explanation of spending patterns.
- **Import instead of typing** — Import transactions from a linked Plaid Sandbox test account.

## Product/MVP Delivery

| Sprint | Planned focus |
| --- | --- |
| Sprint 1 | Sign up, sign in, enter income and expenses, and see a remaining balance. |
| Sprint 2 | Correct entries, view category spending, receive low-balance warnings, and reset a password. |
| Sprint 3 | Explain monthly spending with the OpenAI API, scan receipts with RapidOCR, and manage recurring-expense schedules and reminders. |
| Sprint 4 | Import transactions from Plaid Sandbox without duplicate entries. |

The initial receipt-scanning choice is RapidOCR. We will evaluate its receipt-total extraction and integration effort, and consider Amazon Textract if reliability or development time makes RapidOCR unsuitable.

## AI Usage Logs

> This section documents where and when Team 3 used AI assistance. It records the tool used, what it supported, and how the team used the result.

### Sprint 0-2: Sep 28, 2026

**Tool:** Claude Code

**What it helped with:**

- Broke down the Sprint 0-2 requirements and rubric, and summarized Team 4's BudgetWise pitch deck
- Generated a blank template for the Sprint 0-2 document with a section for each graded requirement
- Created mock lo-fi wireframes (6 screens) and a screen navigation diagram based on Team 4's pitch (scrapped)

**How we used the result:**

We used the template as the outline for our Sprint 0-2 document and wrote the user stories, Gherkin, storyboards and sprint plan ourselves. We used the mock wireframes as a starting point and revised them to match our high-level stories.

### Sprint 0-2: Sep 29, 2026

**Tool:** Codex

**What it helped with:**

- Reviewed gherkins/stories and what we needed to clarify/include before our submission
- Generated storyboard diagrams for each high level story

**How we used the result:**

We used feedback to improve our Gherkins, discuss with ourselves and the customer team to clarify ambiguity, and to ensure we had everything needed for submission. We used the storyboards for our high-level stories required lofi ui step throughs.

### Sprint 0-2: Sep 29, 2026

**Tool:** Codex

**What it helped with:**

- Analyzed pathways for better development of GitHub Board issues, sprint organization, and proper fielding.

**How we used the result:**

Used the feedback to create organized tasks/issues on GitHub, tying with stories and assigning sprints.

### Sprint 0-2: Sep 29, 2026 — follow-up revisions

**Tool:** Codex

**What it helped with:**

- Revised the lo-fi UI into 17 numbered screen sketches, a navigation diagram, and 5 high-level storyboards in response to the review feedback from Pardot.

**How we used the result:**

We replaced the earlier visuals in the Sprint 0-2 document with the revised sketches and updated the supporting text.

### Sprint 0-3: Oct 5, 2026

**Tool:** Codex

**What it helped with:**

- Reviewed the initial Django setup and removal of the generated secret key from source.
- Helped describe the changes in commits and reconcile the README with the latest `main` branch.

**How we used the result:**

We checked the local Django project, updated its setup instructions, and kept the current Sprint 0-2 project details while adding Sprint 0-3 documentation.

### Sprint 0-3: Oct 5, 2026 — deployment

**Tool:** Codex

**What it helped with:**

- Documentation of deployment steps and architecture decisions
- Configuring the domain settings properly
- Prepared the Lambda adapter
- Wrote tests for AWS Aurora PostgreSQL initial configuration
- Wrote CI yaml for testing Django against temporary PostgreSQL
- Wrote CD yaml for Lambda deployment workflow
- Reviewed deployment checks, package handling, and rollback behavior, suggested improvements

**How we used the result:**

The initial scaffold is now running at the registered public URL. Lambda is properly invoked through API Gateway and running our Django code to deploy the application.

### Sprint 1: Oct 12, 2026 — automated review and coverage

**Tool:** Codex

**What it helped with:**

- Prepared Luna PR review with related issue and Gherkin context.
- Added coverage reporting, the 80% line coverage gate, and automated tests.

**How we used the result:**

We verified the implementation locally with unit/integration tests, Behave scenarios,
PostgreSQL, coverage reports, and workflow linting. Changes remain local for human
review and delivery; live API review still needs verification after merging to `main`.

### Sprint 1: Oct 17, 2026 — Recording Income

**Tool:** Codex

**What it helped with:**

- Reviewed the D3 acceptance criteria and existing transaction model.
- Drafted the income form and focused tests for the specified valid and zero-amount inputs.
- Drafted the basic income HTML page, protected view, URL, and page test.
- Drafted the Save income button, POST handling, and tests for valid and zero-amount submissions.
- Drafted tests and feedback for a missing income source and a successful save.
- Helped style the income page and add the BudgetWise home link.

**How we used the result:**

We kept the model as the source of the amount rule and used a model-backed form for
browser input. Fabian chose an explicit GET/POST branch for clarity. He manually ran
the tests, saved an income entry on the local site and verified its date, type, and
amount in Django admin, checked the zero-amount error and absence of a saved row,
and confirmed an incognito visitor is redirected. The full Django suite passed with
54 tests. Fabian also checked the missing-source error, save confirmation, and
updated page locally. Entries are not yet associated with users or shown in a budget.

### Sprint 1: Oct 17, 2026 — review eligibility

**Tool:** Codex

**What it helped with:** Diagnosed silent AI-review skips and prepared current-PR
eligibility checks with visible failures.

**How we used the result:** Checked the workflow boundaries and exercised eligible,
ineligible, and failure cases locally before human delivery.

### Sprint 1: Oct 18, 2026 — Account foundation

**Tool:** Codex

**What it helped with:** Reviewed the shared email identity contract, prepared focused
tests, and foundation Behave scenarios for #10.

**How we used the result:** Added email normalization and account creation using
the existing Django user model, with tests for input validation, password handling,
and duplicate protection.

### Sprint 1: Oct 19, 2026 — Calendar month budget integration

**Tool:** Codex

**What it helped with:**

- Integrated the monthly budget work with the latest main branch and resolved conflicts.
- Verified the budget and demo-data behavior, added issue #21 acceptance scenarios,
  and prepared the commit and pull request.

**How we used the result:**

We reviewed the dashboard locally and retained the demo-only scope while combining
it with the team's income form and landing-page styling.

### Sprint 1: Oct 19, 2026 — Recording Expenses

**Tool:** Claude Code

**What it helped with:**

- Reviewed the D-4 acceptance criteria and the existing income form, view, and tests.
- Drafted the expense form, protected view, URL, page, and focused tests, written
  before the implementation.
- Reviewed the change for access control, field tampering, and markup issues, and
  added the missing-category Behave scenario.

**How we used the result:**

We followed the income pattern so the two pages behave the same, kept the category
list in the form so the change needed no migration, and left out the transaction-list
and remaining-budget criteria until expenses are tied to users. Noah chose the
category list and the issue reference.

### 2026-10-19 — Database email uniqueness

**Tool:** Codex

**What it helped with:** Added database enforcement of unique email identities and
ASCII normalization with international-domain conversion.

**How we used the result:** Kept Django's default user model and checked duplicate
inserts and updates on SQLite and PostgreSQL.

### Sprint 1: Oct 21, 2026 — Transaction ownership

**Tool:** Codex

**What it helped with:**

- Added ownership assertions to the existing income and expense save tests.
- Added the signed-in user to each transaction before saving it.

**How we used the result:**

Fabian ran each focused test with the ownership assertion failing before the view
change, then passing after it. New income and expense entries now belong to the
signed-in student. The optional owner field still allows older and demo records
without an owner. The later D2 dashboard displays only user-owned records.

### Sprint 1: Oct 21, 2026 — Pending success scenarios and shared Behave steps

**Tool:** Claude Code

**What it helped with:**

- Drafted the "Paycheck is recorded" and "Fixed expense is recorded" Behave
  scenarios and their steps, and the `behave.ini` setting that skips `@wip`.
- Moved the shared sign-in setup and checks into `common_steps.py`.

**How we used the result:**

Following Pardot's advice, we added both scenarios now as pending instead of waiting
for D2, and kept them skipped in CI rather than faking a passing step. We checked
that both pass once the dashboard shows the student's own transactions, and that a
wrong error message still fails the expense scenario.

### Sprint 1: Oct 22, 2026 — Complete D1 and connect D2 navigation

**Tool:** Codex

**What it helped with:** Signup email, single-use verification, the password form,
and integration of D1 signup with D2 sign-in and transaction navigation.

**How we used the result:** Reused Django auth/mail and the shared identity helpers,
combined the unshipped D1 migrations after D2, and added focused route and
acceptance checks. Added the application sign-in gate and shared account/recording
navigation; dashboard changes remain in D2 (#53).

### Sprint 1: Oct 22, 2026 — Student sign-in and account lockout

**Tool:** ChatGPT

**What it helped with:**

- Reviewed D2 implementation against GitHub issue #11 and PR feedback.
- Added Django tests for login lockout, expiration, rolling failure windows, logout, dashboard privacy, and stale-attempt cleanup.
- Implemented the five official Gherkin acceptance scenarios using Behave.
- Added a PostgreSQL-specific concurrency test and a management command for cleaning up stale login attempts.
- Helped integrate the authenticated monthly dashboard with existing transaction ownership.

**How we used the result:**

We reviewed and adapted the suggestions to the existing Django project and its acceptance criteria.

### Sprint 1: Oct 22, 2026 — Sign-in follow-up and dashboard integration

**Tool:** Codex

**What it helped with:** Reviewed PR #53 feedback, prepared focused regressions,
and simplified sign-in retention, request limits, routes, and deployment checks.

**How we used the result:** Kept one private dashboard, removed the legacy demo
route, and used the database for shared limits and automatic cleanup without new
services. Retained focused tests and the existing deployment rollback path.

### Sprint 2: Oct 28, 2026 — Password-reset core

**Tool:** Codex

**What it helped with:** Drafted the password-reset core with tests and independent reviews.

**How we used the result:** Reused Django reset tokens and password validation,
kept password replacement and lockout clearing in one transaction, and added
core acceptance scenarios. Email delivery and reset pages remain separate work.

### Sprint 2: Oct 29, 2026 — CI feedback follow-up

**Tool:** Codex

**What it helped with:** Added all-branch deterministic lint, dependency auditing, and focused
acceptance checks.

**How we used the result:** Kept the existing test/coverage job and human delivery
process, checked intentional lint failures, and approved the certifi dependency
update identified by the first audit. Switched the linter to Flake8 for the
Sprint 3 requirement, reusing the existing checks. Operational monitoring remains
separate.

### Sprint 2: Oct 31, 2026 — Spending by category

**Tool:** Claude Code

**What it helped with:**

- Reviewed the D-7 acceptance criteria, the dashboard month selector, and the
  existing expense categories.
- Drafted the category totals page, its tests and the Behave scenario, written
  before the implementation.
- Checked the page in a local browser at desktop and phone widths.

**How we used the result:**

We kept the breakdown on its own page so it does not conflict with other dashboard
work, used plain HTML and CSS bars instead of a chart library, and matched the
dashboard's month rules. Noah chose to deliver the story as one pull request.
