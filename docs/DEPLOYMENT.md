# BudgetWise Deployment

Chase will maintain the AWS setup for Team 3. Local development follows the README and uses SQLite.

## Request flow

`budget-wise.dev → API Gateway → Lambda → Django`

Cloudflare manages DNS. API Gateway calls the `live` alias of Lambda function `budgetwise-demo` in `us-east-1`. Lambda uses Python 3.13, x86_64, and handler `lambda_entry.handler`.

`src/lambda_entry.py` uses Mangum to translate requests for Django. It disables debug output, accepts our domain, and requires HTTPS and secure cookies. These overrides only apply when Lambda loads the adapter.

## Configuration

Set `DJANGO_SECRET_KEY` in Lambda to a private, randomly generated value of at least 50 characters. Never commit its value. Dependencies are recorded in `requirements.txt`.

The deployment ZIP needs the contents of `src/` and installed dependencies at its root. Exclude local databases, `.env` files, virtual environments, and caches. GitHub Actions will build this ZIP as part of CD.

## Release and rollback

The planned workflow checks the code, builds the ZIP, publishes a Lambda version, tests it, and moves `live` to that version. Until that workflow is configured, releases remain manual.

Record the previous version before moving `live`. To roll back code, point the alias at that previous version. Database changes need their own recovery plan; changing the alias does not undo migrations.

## Current status

- The initial scaffold is deployed; `/` returns Django's production 404.
- Aurora connectivity, application migrations, and a database-backed view are pending. SQLite in a Lambda package is not persistent application storage.
- Automated deployment and its AWS permissions are pending.
- Verify a release with a small number of requests and check `/aws/lambda/budgetwise-demo` logs for failures. A 404 is expected only while the homepage is missing.
