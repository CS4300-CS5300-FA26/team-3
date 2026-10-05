# BudgetWise Deployment

Chase will maintain the AWS setup for Team 3. Local development follows the README and uses SQLite.

## Request flow

`budget-wise.dev → API Gateway → Lambda → Django`

Cloudflare manages DNS. API Gateway calls the `live` alias of Lambda function `budgetwise` in `us-east-1`. Lambda uses Python 3.13, x86_64, and handler `lambda_entry.handler`.

`src/lambda_entry.py` uses Mangum to translate requests for Django. It disables debug output, accepts our domain, and requires HTTPS and secure cookies. These overrides only apply when Lambda loads the adapter.

## Configuration

Set `DJANGO_SECRET_KEY` in Lambda to a private, randomly generated value of at least 50 characters. Never commit its value. Dependencies are recorded in `requirements.txt`.

The deployment ZIP needs the contents of `src/` and installed dependencies at its root. Exclude local databases, `.env` files, virtual environments, and caches. GitHub Actions will build this ZIP as part of CD.

## Database

Aurora PostgreSQL cluster `budgetwise` is our application database in `us-east-1`, configured for 0–1 ACU and automatic pause after five idle minutes. Use local tests to conserve credits.

Without `DB_HOST`, Django uses local SQLite. To select Aurora, set:

| Variable | Value |
| --- | --- |
| `DB_HOST` | Aurora writer endpoint from the AWS console |
| `DB_NAME` | `budgetwise` |
| `DB_USER` | `budgetwise_app` for the web app; `budgetwise_migrator` for migrations |
| `AWS_REGION` | `us-east-1` |

The backend in `src/budgetwise/db/aurora/` generates a fresh IAM token for each connection and verifies the server certificate. Lambda uses its IAM role; teammates do not need AWS access to develop or test their code. No Aurora password is stored. Connections close after each request so Aurora can pause to avoid wasting usage credits.

Keep the actual hostname in environment configuration rather than source control. We currently use the single writer's instance endpoint; update it if the writer is replaced. Local database-connection tests run with `python -m unittest discover -s tests` and make no AWS calls.

The app user can read and write records. The migration user can create tables and grants the app access to new tables. Run `python src/manage.py migrate` with the migration user's connection settings when deploying migrations. Keep routine tests local; don't run Django's test database creation against Aurora.

## Release and rollback

CI uses `budgetwise.ci_settings` and a temporary PostgreSQL 17 service on the GitHub runner. Its fixed password is only for that disposable database. Local development uses SQLite; the deployed app uses Aurora once activated. These databases do not share data.

The planned workflow checks the code, builds the ZIP, publishes a Lambda version, tests it, and moves `live` to that version. Until that workflow is configured, releases remain manual.

Record the previous version before moving `live`. To roll back code, point the alias at that previous version. Database changes need their own recovery plan; changing the alias does not undo migrations.

## Current status

- The initial scaffold is deployed; `/` returns Django's production 404.
- Aurora and its two database users are configured. Activating the connection in Lambda, application migrations, and a database-backed view are pending.
- Automated deployment and its AWS permissions are pending.
- Verify a release with a small number of requests and check `/aws/lambda/budgetwise` logs for failures. A 404 is expected only while the homepage is missing.
