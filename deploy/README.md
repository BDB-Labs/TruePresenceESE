# TruePresence Cloud Deployment Guide

This deploy path starts the product runtime from `main:app`, which imports
`truepresence.main:app`. Use `/health` for liveness and `/ready` for deployment
readiness.

## Required Production Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Yes | Long random secret used to sign dashboard/API JWTs. |
| `DATABASE_URL` | Yes | PostgreSQL connection string for users, Telegram tokens, sessions, and reviews. |
| `TELEGRAM_BOT_TOKEN` | Yes | Default tenant bot token from BotFather. Per-tenant variants use `TELEGRAM_BOT_TOKEN_<TENANT>`. |
| `TELEGRAM_WEBHOOK_SECRET` | Yes | Secret token Telegram must send in `X-Telegram-Bot-Api-Secret-Token`. |
| `TRUEPRESENCE_ENCRYPTION_KEY` | Yes | Fernet key used when storing Telegram bot tokens through `/telegram/tokens`. |
| `BASE_URL` | Yes | Public HTTPS origin used when configuring Telegram webhooks. |
| `PORT` | No | Platform-provided port. Defaults to `8000`. |
| `REDIS_URL` | No | Enables distributed session/cache storage. If set, `/ready` requires Redis to be reachable. |

Do not set `TRUEPRESENCE_ALLOW_DEV_AUTH` or `TRUEPRESENCE_ALLOW_LENIENT_WIRING`
in production.

## Railway

1. Connect the GitHub repo to Railway.
2. Add PostgreSQL and link `DATABASE_URL`.
3. Set the required production variables above.
4. Deploy with the existing Railway start command.
5. Configure the Telegram webhook:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$BASE_URL/telegram/webhook?tenant=default" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

## Fly.io / Docker

The Docker image uses `/ready` as its container health check and expands the
runtime `PORT` through a shell command.

```bash
flyctl secrets set \
  JWT_SECRET=replace-with-long-random-secret \
  DATABASE_URL=postgresql://... \
  TELEGRAM_BOT_TOKEN=123456:telegram-token \
  TELEGRAM_WEBHOOK_SECRET=replace-with-webhook-secret \
  TRUEPRESENCE_ENCRYPTION_KEY=replace-with-fernet-key \
  BASE_URL=https://your-app.fly.dev

flyctl deploy
```

## Render

Use the Python service path, not the dashboard Node build, for the backend:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Health check path: `/ready`

Set the required production variables before enabling deploys.

## Verification

```bash
curl "$BASE_URL/health"
curl -f "$BASE_URL/ready"
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

`/health` returns component status for diagnostics. `/ready` returns HTTP 503
when PostgreSQL is unavailable, or when Redis is configured but unavailable.

## Production Checklist

- [ ] `JWT_SECRET` is set and not shared with development.
- [ ] `DATABASE_URL` points at migrated PostgreSQL.
- [ ] Initial admin user has been seeded.
- [ ] `TELEGRAM_BOT_TOKEN` or tenant-specific bot tokens are set.
- [ ] `TELEGRAM_WEBHOOK_SECRET` is set and passed to Telegram.
- [ ] `TRUEPRESENCE_ENCRYPTION_KEY` is set before storing bot tokens.
- [ ] `/health` returns diagnostics.
- [ ] `/ready` returns HTTP 200.
- [ ] Telegram `getWebhookInfo` shows the expected webhook URL and no delivery errors.
