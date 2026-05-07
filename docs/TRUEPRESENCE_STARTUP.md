# TruePresence Startup Guide

This guide covers the product runtime in this repository. ESE remains available
as the ensemble framework, but TruePresence starts from `truepresence.main:app`
and the Next.js dashboard in `truepresence/ui`.

## Prerequisites

- Python 3.10 or newer. The local virtualenv in this repo uses Python 3.11.
- Node.js and npm for the dashboard.
- PostgreSQL for persistent auth, users, Telegram sessions, and reviews.
- Redis is optional. Set `REDIS_URL` only when you want distributed session
  storage.

## Backend Setup

Create and install the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,test]"
```

For a local smoke test without Postgres, use explicit development mode:

```bash
export TRUEPRESENCE_ENV=development
export TRUEPRESENCE_ALLOW_DEV_AUTH=true
export TRUEPRESENCE_ALLOW_LENIENT_WIRING=true
export PORT=8000

uvicorn truepresence.main:app --reload --host 127.0.0.1 --port "$PORT"
```

Verify:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/api/health
```

The development mode above is only for local startup checks. Production must set
`JWT_SECRET`.

## Persistent Local Backend

Use Postgres when you need login, admin users, persistent Telegram sessions, or
review queues:

```bash
docker run --name truepresence-postgres \
  -e POSTGRES_USER=truepresence \
  -e POSTGRES_PASSWORD=truepresence \
  -e POSTGRES_DB=truepresence \
  -p 5432:5432 \
  -d postgres:16

export DATABASE_URL=postgresql://truepresence:truepresence@127.0.0.1:5432/truepresence
export JWT_SECRET=replace-with-a-long-random-secret
export TRUEPRESENCE_ENV=development
```

Seed the first admin:

```bash
ADMIN_EMAIL=admin@example.com \
ADMIN_PASSWORD=change-me \
ADMIN_NAME="TruePresence Admin" \
python seed_admin.py
```

Then start the backend:

```bash
uvicorn truepresence.main:app --reload --host 127.0.0.1 --port 8000
```

## Dashboard Setup

Run the dashboard against the local backend:

```bash
cd truepresence/ui
npm install
TRUEPRESENCE_API_URL=http://127.0.0.1:8000 npm run dev
```

Open `http://localhost:3000/dashboard/login` and sign in with the seeded admin.
The UI stores the backend JWT in an HTTP-only cookie through its Next.js API
routes.

## Telegram Startup

Set a bot token for the default tenant:

```bash
export TELEGRAM_BOT_TOKEN=123456:telegram-token
export TELEGRAM_WEBHOOK_SECRET=replace-with-telegram-webhook-secret
export BASE_URL=https://your-public-domain.example
```

Recommended webhook shape:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$BASE_URL/telegram/webhook?tenant=default" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

Per-tenant tokens use an uppercase tenant suffix:

```bash
export TELEGRAM_BOT_TOKEN_CLIENT1=123456:client1-token
export TENANT_NAME_CLIENT1="Client 1"
```

Then use `?tenant=client1` or the `X-Tenant-ID: client1` header on management
requests.

## Production Environment

Set these before deploying:

```bash
JWT_SECRET=long-random-production-secret
DATABASE_URL=postgresql://...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
TRUEPRESENCE_ENCRYPTION_KEY=fernet-key-for-stored-telegram-tokens
BASE_URL=https://your-public-domain.example
PORT=8000
```

Optional:

```bash
REDIS_URL=redis://...
TRUEPRESENCE_IDENTITY_HASH_SECRET=long-random-secret
```

Do not set `TRUEPRESENCE_ALLOW_DEV_AUTH` or
`TRUEPRESENCE_ALLOW_LENIENT_WIRING` in production.

## Verification

Install the Python and dashboard test dependencies before running the full
local checks:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev,test]"
cd truepresence/ui
npm ci
cd ../..
```

Full Python suite:

```bash
PYTHONPATH=. pytest -q
```

Focused SDK tests:

```bash
PYTHONPATH=. pytest \
  tests/truepresence/test_sdk_api.py \
  tests/truepresence/test_sdk_privacy.py \
  tests/truepresence/test_sdk_scoring.py \
  -q
```

Optional integration and Telegram guardrail tests:

```bash
PYTHONPATH=. pytest \
  tests/test_truepresence_architecture.py \
  tests/truepresence/test_telegram_*.py \
  -q
```

These tests are marked with `integration`, `db`, `rate_limit`, and `telegram`
where applicable. Modules that import PostgreSQL-backed or rate-limit wiring
use `pytest.importorskip`, so SDK-only runs can still execute when
`psycopg2-binary` or `slowapi` is not installed.

Browser SDK tests:

```bash
node --test tests/browser-sdk/truepresence-browser-sdk.test.mjs
```

Backend compile and lint checks:

```bash
python -m compileall -q truepresence ese main.py
git ls-files '*.py' | xargs ruff check
```

Dashboard lint and build:

```bash
cd truepresence/ui
npm run lint
npm run build
```

Whitespace check:

```bash
git diff --check
```

Note: run Ruff only on Python files. The repository also contains JavaScript,
TypeScript, JSON, and TSX assets that Ruff will report as invalid Python.

## Dependency Alert Follow-Ups

Current open alerts need targeted follow-up rather than broad dependency churn:

- `ecdsa` is pulled through the current Python auth dependency path and has no
  patched release listed by Dependabot. Treat this as a follow-up to replace or
  isolate the vulnerable dependency path.
- The PostCSS advisory is bundled through the current Next.js dependency.
  `npm audit` suggests an unsafe downgrade path instead of a safe patch, so
  wait for a patched Next.js release or handle it in a dedicated dependency
  update.

## Troubleshooting

- `JWT_SECRET is required`: set `JWT_SECRET`, or for local-only smoke tests set
  both `TRUEPRESENCE_ENV=development` and `TRUEPRESENCE_ALLOW_DEV_AUTH=true`.
- Login fails while health checks pass: configure `DATABASE_URL` and run
  `python seed_admin.py`.
- `/ready` returns HTTP 503: configure PostgreSQL, and if `REDIS_URL` is set,
  make sure Redis is reachable.
- Telegram webhook returns unauthorized: if `TELEGRAM_WEBHOOK_SECRET` is set,
  Telegram must send the matching `X-Telegram-Bot-Api-Secret-Token` header.
- Redis connection errors: unset `REDIS_URL` for a local single-process run, or
  start Redis before the backend.
