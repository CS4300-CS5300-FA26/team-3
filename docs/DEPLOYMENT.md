# BudgetWise Deployment

Chase will maintain the AWS setup for Team 3. Local development follows the README and uses SQLite.

## Request flow

`budget-wise.dev → Cloudflare → API Gateway → Lambda → Django`

Cloudflare manages DNS and proxies the main domain using Full (strict) TLS. API Gateway calls the `live` alias of Lambda function `budgetwise` in `us-east-1`. Lambda uses Python 3.13, x86_64, and handler `lambda_entry.handler`.

`src/lambda_entry.py` uses Mangum to translate requests for Django. It disables debug output, accepts our domain, and requires HTTPS and secure cookies. These overrides only apply when Lambda loads the adapter.

## Public traffic protections

Chase maintains these Cloudflare Free-plan settings for the Team 3 school demo, configured on October 6, 2026. The site remains public; these controls do not identify classmates or replace application authentication.

| Control | Configuration |
| --- | --- |
| Main-domain DNS | Existing API Gateway CNAME is proxied; its target is unchanged. Certificate-validation and email records remain DNS-only. |
| Scanner blocking | `BudgetWise - block common scanner paths` blocks `/.env`, `/.env.*`, `/.git`, `/.git/…`, `/wp-login.php`, `/wp-admin`, `/wp-admin/…`, and `/xmlrpc.php` on the main hostname. Django's `/admin/` is unaffected. |
| Rate limiting | `BudgetWise - dynamic requests 10 per 10 seconds` counts requests per IP, excluding paths beginning `/static/`, and blocks for 10 seconds after exceeding 10 requests in 10 seconds. |
| Deployment compatibility | `BudgetWise - deployment health check compatibility` skips only Browser Integrity Check for main-hostname `GET /` requests with an empty query string and a user-agent beginning `Python-urllib/`. Rate limiting and other rules still apply. |
| AWS backstop | API Gateway's default endpoint is disabled; its default stage throttle is 1 request/second with burst 2. |

Browser Integrity Check remains enabled generally. The narrow exception is needed because the existing Python deployment check otherwise receives Cloudflare error 1010. A user-agent is spoofable and is not proof of deployment identity. Bot Fight Mode remains off to avoid browser challenges breaking automated checks.

Cloudflare rate limiting is best effort, not a spending cap. Campus users may share an IP and briefly hit the same limit. Slow requests, excluded static paths, and traffic reaching the AWS origin outside Cloudflare are not eliminated by this setup; origin-only access enforcement remains future work. Preserve AWS Free Plan access and credits: do not upgrade plans or add paid services, and use local tests plus bounded live verification.

For failures, inspect Cloudflare Security Analytics and the existing Lambda logs. A normal homepage request should match `ROOT_STATUS`; a blocked scanner path should return Cloudflare 403. On October 6, the homepage returned the same 404 body before and after proxying, `www` returned its 301 redirect, and requests 11–12 of a bounded 12-request probe to an unused path received Cloudflare 429/error 1015. Earlier 429 responses in that probe came from AWS throttling. No database-query test or AWS configuration change was performed.

To undo an overstrict rule, disable that named rule in Cloudflare → Security → Security rules. For a proxy compatibility failure, restore only the main-domain record to DNS-only, retaining its target and certificate-validation records; cached DNS answers may take time to expire. The DNS rollback was exercised during setup and the original route returned the expected 404 with valid TLS. Keep the compatibility exception active while the main domain is proxied and CD uses Python urllib.

## Configuration

Set `DJANGO_SECRET_KEY` in Lambda to a private, randomly generated value of at least 50 characters. Never commit its value. Dependencies are recorded in `requirements.txt`.

GitHub Actions builds the deployment ZIP from `src/` and Linux-compatible dependencies, excluding local databases, `.env` files, virtual environments, and caches.

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

Keep the actual hostname in environment configuration rather than source control. We currently use the single writer's instance endpoint; update it if the writer is replaced. Run local tests with `python src/manage.py test tests src`; database-connection tests use mocks and make no AWS calls.

The app user can read and write records. The migration user can create tables; its new tables automatically grant the app access. CD runs migrations using that role. Keep routine tests local; don't run Django's test database creation against Aurora.

## Release and rollback

CI uses `budgetwise.ci_settings` and a temporary PostgreSQL 17 service. Its fixed password is only for that disposable database. Local SQLite, CI PostgreSQL, and deployed Aurora do not share data.

`.github/workflows/cd.yml` runs after application or workflow changes merge into `main`, or manually through Actions → Deploy on `main`:

1. Run CI and build one ZIP in a job without AWS access.
2. Download that exact ZIP, reject stale `main` revisions, and obtain temporary AWS credentials through GitHub OIDC.
3. Apply Aurora migrations from the ZIP and publish it as a new Lambda version.
4. Check that version's database connection and homepage before moving `live` to it.
5. Check the public URL; restore the previous version if this check fails.

The package is retained in GitHub Actions for one day. If it expires, rerun the entire workflow to rebuild it. If an alias-update response is lost, CD reads the alias back before continuing; it does not overwrite a conflicting change.

The AWS role `budgetwise-github-deploy` trusts only this repository's `main` branch. It can deploy this Lambda and connect as the migration user. No AWS access keys or teammate AWS accounts are needed.

GitHub Actions settings:

| Setting | Purpose |
| --- | --- |
| Variable `AWS_DEPLOY_ROLE_ARN` | Deployment role ARN |
| Variable `ROOT_STATUS` | Expected homepage status: `404` now; set to `200` when the homepage is added |
| Secret `DB_HOST` | Same Aurora writer endpoint as Lambda |

The workflow reports the previous Lambda version. For a later code rollback, point `live` back to it in Lambda's Aliases tab. This does not undo migrations: keep schema changes compatible with the previous release.

## Current status

- The initial scaffold is deployed; `/` returns Django's production 404.
- Aurora, its database users, Lambda environment, and GitHub deployment permissions are configured. The live version still uses the initial scaffold.
- The transaction model and migrations are implemented. The first Actions deployment and a public database-backed view remain pending.
- Verify a release with a small number of requests and check `/aws/lambda/budgetwise` logs for failures. A 404 is expected only while the homepage is missing.
