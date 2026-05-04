# 🤖 Telegram Middleman Bot

A **production-ready** privacy-first Telegram bot that acts as a secure relay between
users and an owner — without ever exposing the owner's Telegram identity.

---

## ✨ Features

| Category | Details |
|---|---|
| **Privacy** | Owner identity fully hidden; users identified by `@handle` or anonymous `User #xxxx` |
| **Media** | Text, photo, video, document, audio, voice, sticker |
| **Commands** | `/start`, `/help` (users) · `/stats`, `/broadcast` (owner) |
| **Database** | MongoDB with indexed collections for fast routing |
| **Rate limiting** | Sliding-window per-user limiter (configurable) |
| **Reliability** | Structured logging, graceful error handling, startup health check |

---

## 📁 File Structure

```
telegram_middleman_bot/
├── main.py                  # Entry point — bot startup & dispatcher
├── config.py                # Typed env-var loader
├── db.py                    # MongoDB helpers, indexes, upserts
├── requirements.txt
├── .env.example
├── handlers/
│   ├── __init__.py
│   ├── user.py              # /start, /help, message forwarding
│   └── owner.py             # /stats, /broadcast, reply routing
└── services/
    ├── __init__.py
    ├── rate_limiter.py      # Sliding-window rate limiter
    └── router.py            # Forward & reply logic (media-aware)
```

---

## ⚙️ Setup

### 1 — Prerequisites

- Python 3.11+
- MongoDB 6+ (local or [Atlas free tier](https://www.mongodb.com/atlas))
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 2 — Get your Telegram User ID

Message [@userinfobot](https://t.me/userinfobot) on Telegram — it replies with your numeric ID.

### 3 — Install dependencies

```bash
cd telegram_middleman_bot
pip install -r requirements.txt
```

### 4 — Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OWNER_ID=987654321
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=middleman_bot
```

### 5 — Start MongoDB (local)

```bash
# macOS (Homebrew)
brew services start mongodb-community

# Linux (systemd)
sudo systemctl start mongod

# Docker
docker run -d -p 27017:27017 --name mongo mongo:7
```

### 6 — Run the bot

```bash
python main.py
```

You should see:

```
2024-01-15 10:00:01 | INFO     | __main__ | Logged in as @YourBotName (id=7123456789)
2024-01-15 10:00:01 | INFO     | __main__ | Owner ID: 987654321
2024-01-15 10:00:01 | INFO     | db       | MongoDB indexes verified / created.
2024-01-15 10:00:01 | INFO     | __main__ | Entering long-poll loop.
```

---

## 💬 Sample Interaction

```
━━━ USER SIDE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User → Bot:   /start
Bot  → User:  👋 Hello! Send me a message and I'll pass it along.

User → Bot:   Hi, I'd like to ask about your services
Bot  → User:  ✅ Your message has been sent!

━━━ OWNER SIDE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bot → Owner:  📩 Message from @alice:
              Hi, I'd like to ask about your services

Owner → Bot:  [replies to that message ↑]
              Sure! What would you like to know?

Bot → Owner:  ✅ Reply delivered.

━━━ BACK TO USER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bot → User:   Sure! What would you like to know?
```

---

## 🔑 Owner Commands

| Command | Description |
|---|---|
| `/stats` | Shows total registered users |
| `/broadcast Hello everyone!` | Sends a message to all users |
| Reply to any forwarded message | Routes your reply back to that user |

---

## 🛡️ Security Notes

- **OWNER_ID** is the only authorization mechanism — keep it secret.
- Users are shown as `@username` or `User #4f2a` (last 4 hex chars of their numeric ID). Their raw Telegram ID is never displayed.
- Users cannot see each other; all messages are routed 1-to-owner privately.
- The rate limiter (default: 5 messages per 60 s) prevents spam floods.

---

## 🌐 Production Deployment (systemd)

```ini
# /etc/systemd/system/middleman-bot.service
[Unit]
Description=Telegram Middleman Bot
After=network.target mongod.service

[Service]
WorkingDirectory=/opt/middleman_bot
EnvironmentFile=/opt/middleman_bot/.env
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now middleman-bot
sudo journalctl -fu middleman-bot
```

---

## 🔮 Optional Enhancements (not included — extend as needed)

- **Webhook mode** — replace `start_polling` with aiogram's webhook runner for lower latency
- **Redis rate limiter** — swap `services/rate_limiter.py` for a Redis-backed counter for multi-process deployments
- **Auto-away reply** — set `AWAY_MESSAGE` in `.env`; hook into `handle_user_message` to send it if the owner hasn't replied within N hours
- **Admin CLI** — add a `cli.py` using Click/Typer that queries MongoDB directly for stats and message history
- **Anonymous toggle** — add a `/anon` command that lets users opt-in to full anonymity (store flag in `users` collection)
