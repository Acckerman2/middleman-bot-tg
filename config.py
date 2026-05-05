"""
config.py — Centralised environment configuration.

All settings are loaded once at import time.  Any missing required
variable raises a clear RuntimeError so the bot fails fast rather
than silently misbehaving.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Return env var or raise if absent."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. "
            "Check your .env file."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Required ──────────────────────────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")
OWNER_ID: int = int(_require("OWNER_ID"))
MONGO_URI: str = _require("MONGO_URI")

# ── Optional / defaults ───────────────────────────────────────────────────────
MONGO_DB_NAME: str = _optional("MONGO_DB_NAME", "middleman_bot")

WELCOME_MESSAGE: str = _optional(
    "👋 Welcome!",
    "You may send your message here, and it will be securely forwarded to the owner. Your identity and personal details are kept strictly confidential and will not be disclosed. "
    " ⏱️ Responses are typically provided within a few hours.  Please type your message to begin.",
)

AWAY_MESSAGE: str = _optional("AWAY_MESSAGE", "")

# Rate limiting
RATE_LIMIT_MESSAGES: int = int(_optional("RATE_LIMIT_MESSAGES", "5"))
RATE_LIMIT_WINDOW: int = int(_optional("RATE_LIMIT_WINDOW", "60"))  # seconds

# Logging
LOG_LEVEL: str = _optional("LOG_LEVEL", "INFO").upper()
