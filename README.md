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

Use Python 3.13 (tested locally with Python 3.13.2). The Django project resides in `src/server/`. Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/server/manage.py check
python src/server/manage.py migrate
python src/server/manage.py runserver 0.0.0.0:3000
```

`check` validates the Django project, and `migrate` creates or updates local SQLite tables. The development server uses port 3000 for DevEdu; use the URL DevEdu provides, or `http://127.0.0.1:3000/` locally. Stop it with `Ctrl+C`. The Django welcome page is expected until the application view is added.

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

**Tool:** Claude Code (Claude Opus 5.5)

**What it helped with:**

- Broke down the Sprint 0-2 requirements and rubric, and summarized Team 4's BudgetWise pitch deck
- Generated a blank template for the Sprint 0-2 document with a section for each graded requirement
- Created mock lo-fi wireframes (6 screens) and a screen navigation diagram based on Team 4's pitch (scrapped)

**How we used the result:**

We used the template as the outline for our Sprint 0-2 document and wrote the user stories, Gherkin, storyboards and sprint plan ourselves. We used the mock wireframes as a starting point and revised them to match our high-level stories.

### Sprint 0-2: Sep 29, 2026

**Tool:** Codex (GPT6.0 Sol)

**What it helped with:**

- Reviewed gherkins/stories and what we needed to clarify/include before our submission
- Generated storyboard diagrams for each high level story

**How we used the result:**

We used feedback to improve our Gherkins, discuss with ourselves and the customer team to clarify ambiguity, and to ensure we had everything needed for submission. We used the storyboards for our high-level stories required lofi ui step throughs.

### Sprint 0-2: Sep 29, 2026

**Tool:** Codex (GPT5.6 Terra)

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
