# TruePresence Cloud Deployment Guide

## Quick Deploy Options

### Option 1: Railway (Easiest - 2 Minutes)

1. **Push to GitHub**
   ```bash
   git add -A
   git commit -m "Add cloud deployment configs"
   git push origin main
   ```

2. **Deploy on Railway**
   - Go to https://railway.app
   - Connect your GitHub repo
   - Click "Deploy Now"

3. **Set Environment Variables**
   - Add `TELEGRAM_BOT_TOKEN` in Railway dashboard

4. **Get your URL**
   - Railway provides: `https://truepresence-telegram.up.railway.app`

5. **Set Telegram Webhook**
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-railway-url.webhook"
   ```

---

### Option 2: Fly.io (Free - Good Performance)

1. **Install Fly CLI**
   ```bash
   brew install flyctl
   flyctl auth login
   ```

2. **Deploy**
   ```bash
   cd TruePresenceESE
   flyctl deploy
   ```

3. **Set Secrets**
   ```bash
   flyctl secrets set TELEGRAM_BOT_TOKEN=your_token
   ```

4. **Set Webhook**
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-app.fly.dev/webhook"
   ```

---

### Option 3: Render (Free Tier Available)

1. **Push to GitHub**

2. **Create on Render**
   - Go to https://render.com
   - New Web Service
   - Connect GitHub repo
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --bind 0.0.0.0:8000 truepresence.adapters.telegram_bot:app`

3. **Add Environment Variable**
   - `TELEGRAM_BOT_TOKEN`

4. **Set Webhook**
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-render-url.onrender.com/webhook"
   ```

---

## Environment Variables Required

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | YES | Your bot token from @BotFather |
| `PORT` | No | Defaults to 8000 |
| `REDIS_URL` | No | For distributed sessions (optional) |

---

## Verify It's Working

1. **Check health endpoint**
   ```bash
   curl https://your-url/health
   ```

2. **Check Telegram bot started**
   - Send `/start` to your bot
   - Should get response

3. **Check webhook set**
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```

---

## Troubleshooting

### Bot not responding?
- Check logs: `flyctl logs` or Railway dashboard logs
- Verify webhook: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"`

### Bot crashes immediately?
- Check environment variables are set
- Run locally first: `python -m truepresence.adapters.telegram_bot`

### Getting 502 errors?
- Health check might be failing
- Check that port is 8000 and gunicorn is binding correctly

---

## Production Checklist

- [ ] Telegram bot token set
- [ ] Webhook URL set in Telegram
- [ ] Health endpoint responding
- [ ] Bot responds to /start command
- [ ] Logs show no errors
- [ ] Domain configured (optional for custom domain)