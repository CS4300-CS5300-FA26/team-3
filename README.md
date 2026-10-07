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

`check` validates the Django project, and `migrate` creates or updates local SQLite tables. The development server uses port 3000 for DevEdu; open `http://localhost:3000/` for a local setup. Stop it with `Ctrl+C`. The root page displays synthetic demo transactions stored in the database.

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

## Source layout

- `src/budgetwise/`: Django project settings and URLs.
- `src/budgetwise/db/aurora/`: PostgreSQL connection with AWS IAM authentication.
- `src/transactions/`: transaction model, migrations, and admin registration.
- `src/integrations/`: future Resend, OpenAI, and other service connections.
- `tests/`: transaction, database connection, Lambda, and deployment tests.

## Architecture decisions

Planned request flow: `Browser → API Gateway → Lambda → Django → Aurora PostgreSQL`

| Choice | Reason |
| --- | --- |
| Django views, templates, and ORM | Keep pages, application logic, and database models in one project that the team can develop together. |
| API Gateway and AWS Lambda | Receive HTTPS requests and run Django without maintaining an application server. Mangum translates requests for Django. |
| Aurora PostgreSQL | Keep deployed data independent of Lambda releases. IAM provides temporary database authentication; separate app and migration users limit who can change the schema. |
| SQLite locally; temporary PostgreSQL in CI | Let teammates develop without AWS accounts and test PostgreSQL compatibility without using Aurora credits. These databases do not share data. |
| Cloudflare DNS and Resend | Cloudflare manages our domain. Resend is selected for application email; its Django integration is still planned. |
| GitHub Actions | Test pull requests and automate releases from `main`, using temporary AWS credentials instead of stored access keys. |

The transaction model and migrations are implemented. The public application page displays synthetic demo transactions from the database while excluding non-demo transactions. See [deployment instructions](docs/DEPLOYMENT.md) for configuration and rollback.

## Deployment

Pull requests to `main` run Django checks, migrations, and tests against a temporary PostgreSQL database in GitHub Actions. This uses no AWS credentials or Aurora credits. Teammates can run local tests with `python src/manage.py test tests src`.

Public URL: https://budget-wise.dev/

API Gateway sends requests to Django on AWS Lambda. The root application view returns a 200 response and displays synthetic demo transactions from the database. The deployment workflow tests changes to `main`, applies migrations, and releases them to Lambda. See [deployment instructions](docs/DEPLOYMENT.md) for configuration and rollback.

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
