# BudgetWise Deployment

Chase maintains the AWS and Resend setup for Team 3. Local setup is documented
in the [README](../README.md).

## Hosting

`budget-wise.dev → Cloudflare → API Gateway → Lambda → Django → Aurora`

Cloudflare provides DNS and public HTTP filtering. API Gateway uses HTTP payload
format 2.0 and invokes the `live` alias of Lambda function `budgetwise` in
`us-east-1`.

| Lambda setting | Value |
| --- | --- |
| Runtime / architecture | Python 3.13 / x86_64 |
| Handler | `lambda_entry.handler` |
| Memory | 1,024 MB |
| Timeout | 30 seconds |
| Temporary storage | 512 MB |
| Package | ZIP |

API Gateway also has a 30-second integration timeout.
[`src/lambda_entry.py`](../src/lambda_entry.py) adapts requests through Mangum,
disables Django debug output, restricts the host to `budget-wise.dev`, and
requires HTTPS and secure cookies. Application dates use `America/Denver`.

## Environment configuration

Set these variables on the Lambda function before publishing a version. Published
versions retain their own configuration; changing `$LATEST` does not change the
version served by `live`. CD preserves function configuration when updating code.
Keep keys and database hostnames out of source control.

| Variable | Value or purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Private random signing key, at least 50 characters |
| `DB_HOST` | Aurora writer instance endpoint |
| `DB_NAME` | `budgetwise` |
| `DB_USER` | `budgetwise_app` |
| `AWS_REGION` | `us-east-1` (provided by Lambda) |
| `RESEND_API_KEY` | Sending-only key restricted to `budget-wise.dev` |
| `SIGNUP_BASE_URL` | Account email link origin; defaults to `https://budget-wise.dev` |
| `OPENAI_API_KEY` | Application key shared by spending explanations and receipt scanning |
| `OPENAI_SPENDING_SUMMARY_MODEL` | Optional; defaults to `gpt-6-luna` |
| `OPENAI_RECEIPT_MODEL` | Optional; defaults to `gpt-6-luna` |

The GitHub AI-review secret is separate from the application's OpenAI key.
Leave `OPENAI_RESPONSES_URL` unset to use the standard OpenAI endpoint.

Spending explanations use a 10-second provider timeout; receipt scans use
20 seconds. Both share the HTTP request budget with database and application
processing. Each feature has a separate database-backed limit of five requests
per student and 100 overall per rolling hour; failed provider calls count.

Receipt uploads accept JPEG, PNG and WebP images up to 4 MiB and 20 million
pixels. The size limit leaves room for base64 encoding within Lambda's
[6 MB synchronous request limit](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html).
Images use temporary files that are removed after processing; there is no receipt
archive. The scanner disables automatic SDK retries and sets `store=False`.

## Database

Aurora PostgreSQL cluster `budgetwise` runs PostgreSQL 17.9 in `us-east-1`, with
one writer, 0.5–1 ACU capacity, auto-pause disabled and one-day backup retention.

The [Aurora backend](../src/budgetwise/db/aurora/base.py) generates a fresh IAM
authentication token for each connection. It uses port 5432, verifies the server
certificate and hostname, and has a 25-second connection timeout.
`CONN_MAX_AGE=0` closes connections after each request. Lambda authenticates with
its execution role; no database password is stored.

The application connects as `budgetwise_app`. CD runs migrations as
`budgetwise_migrator`, whose new tables grant the app access. Keep `DB_HOST` in
Lambda and GitHub Actions synchronized if the writer endpoint changes.

Without `DB_HOST`, Django uses SQLite. CI uses a disposable PostgreSQL 17 service
through `budgetwise.ci_settings`; never run test database creation against Aurora.

## Email and scheduled reminders

Signup, password recovery and expense reminders send from
`accounts@budget-wise.dev` through `smtp.resend.com`, port 465, with implicit TLS
and a five-second timeout. Delivery failures appear in Resend's Emails dashboard.
Revoking the BudgetWise Resend key disables all application email.

The [fixed expense reminder workflow](../.github/workflows/fixed-expense-reminders.yml)
runs daily at 15:17 UTC: 08:17 Mountain standard time or 09:17 daylight time.
It uses GitHub OIDC to invoke `budgetwise:live` with
`{"operation":"send_fixed_expense_reminders"}`. The deployment role requires
`lambda:InvokeFunction` on that alias; there is no public reminder endpoint.

The command uses each student's notice window and records delivery per schedule
and due date. Failed sends remain retryable; past-due expenses are skipped.
A crash between SMTP acceptance and recording delivery can cause a duplicate.
Check failed Actions runs and `/aws/lambda/budgetwise` logs, then rerun from
`main` while the notice window remains open. Disable the workflow in Actions to
stop scheduled reminders while retaining account email.

## Deployment workflow

[Deploy](../.github/workflows/cd.yml) runs for `main` changes under `src/`,
`tests/`, `requirements.txt` or `.github/workflows/`, and supports manual runs
from `main`. Documentation-only changes do not trigger deployment.

| GitHub Actions setting | Purpose |
| --- | --- |
| Variable `AWS_DEPLOY_ROLE_ARN` | ARN of `budgetwise-github-deploy` |
| Variable `ROOT_STATUS` | `200`, the expected sign-in response status |
| Secret `DB_HOST` | Same Aurora writer endpoint used by Lambda |

The deployment role trusts this repository's `main` branch through OIDC.
The workflow:

1. Runs CI and builds a ZIP without AWS credentials.
2. Downloads that exact artifact, rejects stale `main` revisions and obtains temporary AWS credentials.
3. Applies migrations from the package and publishes a Lambda version.
4. Checks the new version's database connection and `/sign-in/` response before moving `live`.
5. Checks the public URL and restores the previous alias target if that request fails.

The package contains `src/` and dependencies from `requirements.txt`, excluding
local databases, environment files and caches. The build accepts
`manylinux2014_x86_64` and `manylinux_2_28_x86_64` wheels for the Python 3.13
Amazon Linux 2023 runtime. Keep the ZIP below 50 MB and unpacked contents,
including layers, below 250 MB. Artifacts are retained for one day; rerun the
workflow if an artifact expires.

## Operations and rollback

Application logs are in `/aws/lambda/budgetwise`. The public deployment probe
follows the root redirect to sign-in and uses
`BudgetWise-Deployment-Check/1.0` as its user agent for Cloudflare compatibility.

CD reports the previous Lambda version. For a code rollback, point `live` back
to that version in Lambda's Aliases tab. CD uses revision checks and reads back
ambiguous alias updates to avoid overwriting another change.

Alias rollback does not undo migrations. Keep schema changes compatible with
the previous application version. Aurora backups provide a separate data-recovery
path; a database restore requires its own operator action.
