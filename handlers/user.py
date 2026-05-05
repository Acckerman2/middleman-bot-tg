"""
handlers/user.py — Handlers for regular (non-owner) users.

Registered routes
-----------------
/start          → register + welcome
/help           → usage instructions
<any message>   → forward to owner (with rate limiting)
"""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

import config
import db
from services.rate_limiter import is_rate_limited
from services.router import forward_to_owner
from services.ai_agent import analyze_message_with_ai

logger = logging.getLogger(__name__)
router = Router(name="user")


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Register user and send the welcome message."""
    user = message.from_user
    try:
        db.upsert_user(user.id, user.username)
    except Exception as exc:  # noqa: BLE001
        logger.error("DB upsert failed for user %d: %s", user.id, exc)

    await message.answer(config.WELCOME_MESSAGE)
    logger.info("User %d started the bot.", user.id)


# ── /help ─────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "ℹ️ <b>How this bot works</b>\n\n"
        "Simply send me any message — text, photo, video, or file — "
        "and it will be forwarded privately.\n\n"
        "You'll receive a reply here once it's been read.\n\n"
        "<b>Commands</b>\n"
        "/start — register & show welcome\n"
        "/help  — show this message"
    )
    await message.answer(help_text, parse_mode="HTML")


# ── Generic message forwarder ─────────────────────────────────────────────────

@router.message()
async def handle_user_message(message: Message, bot: Bot) -> None:
    """
    Forward any message from a regular user to the owner.

    Steps:
    1. Ensure user exists in DB.
    2. Check rate limit.
    3. Forward via router service.
    4. Acknowledge to user.
    """
    user = message.from_user

    # Keep user record fresh
    try:
        db.upsert_user(user.id, user.username)
    except Exception as exc:  # noqa: BLE001
        logger.error("DB upsert failed: %s", exc)

    # Rate limit check
    if is_rate_limited(user.id):
        await message.answer(
            "⚠️ You're sending messages too quickly. "
            "Please wait a moment before trying again."
        )
        logger.warning("Rate-limited user %d", user.id)
        return

    # Use AI to analyze the message
    user_text = message.text or message.caption or "Media attachment sent"
    ai_result = {"reply": "I'm having trouble analyzing your request, forwarding it to the admin.", "is_important": True}
    
    try:
        if user_text:
            ai_result = await analyze_message_with_ai(user_text)
    except Exception as e:
        logger.error("AI Analysis failed: %s", e)

    # Reply to the user with the AI's response
    await message.answer(ai_result["reply"])

    # Forward to owner only if the AI determines it's important
    if ai_result["is_important"]:
        try:
            await forward_to_owner(bot, config.OWNER_ID, message)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error forwarding message from user %d: %s", user.id, exc)
