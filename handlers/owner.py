"""
handlers/owner.py — Handlers that are exclusively available to the bot owner.

All handlers here are guarded by the IsOwner filter.  Any attempt by
a non-owner to trigger these routes is silently ignored (the user
router will catch leftover messages instead).

Owner-only routes
-----------------
/stats      → total registered users
/broadcast  → send a message to all users (reply to this command)
<reply>     → route owner's reply back to the originating user
"""

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

import config
import db
from services.router import route_reply_to_user

logger = logging.getLogger(__name__)
router = Router(name="owner")

# ── Owner filter ──────────────────────────────────────────────────────────────

def _is_owner(message: Message) -> bool:
    return message.from_user.id == config.OWNER_ID


# ── /stats ────────────────────────────────────────────────────────────────────

@router.message(Command("stats"), _is_owner)
async def cmd_stats(message: Message) -> None:
    total = db.count_users()
    await message.answer(f"📊 <b>Bot Statistics</b>\n\nTotal users: <b>{total}</b>", parse_mode="HTML")


# ── /broadcast ────────────────────────────────────────────────────────────────

@router.message(Command("broadcast"), _is_owner)
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    """
    Usage: reply to any message with /broadcast  OR  send:
        /broadcast Your announcement text here

    The bot fans the text out to every registered user with a small
    delay between sends to stay within Telegram rate limits (30 msg/s).
    """
    # Derive broadcast text from command argument or replied-to message
    text: str | None = None

    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        text = args[1].strip()
    elif message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text

    if not text:
        await message.answer(
            "ℹ️ Usage:\n"
            "<code>/broadcast Your message here</code>\n"
            "or reply to a message with /broadcast",
            parse_mode="HTML",
        )
        return

    user_ids = db.get_all_user_ids()
    if not user_ids:
        await message.answer("No users registered yet.")
        return

    sent = failed = 0
    status_msg = await message.answer(f"📡 Broadcasting to {len(user_ids)} users…")

    for uid in user_ids:
        if uid == config.OWNER_ID:
            continue  # skip self
        try:
            await bot.send_message(uid, f"📢 {text}")
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Broadcast failed for user %d: %s", uid, exc)
            failed += 1
        # Throttle: Telegram allows ~30 msg/s; we stay well under at 20/s
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Broadcast complete.\n\nDelivered: {sent}  |  Failed: {failed}"
    )


# ── Reply routing ─────────────────────────────────────────────────────────────

@router.message(_is_owner)
async def handle_owner_reply(message: Message, bot: Bot) -> None:
    """
    Any non-command message from the owner is treated as a reply to a user.

    The owner MUST use Telegram's native reply feature (swipe to reply)
    so we know which forwarded message — and thus which user — to address.
    """
    if not message.reply_to_message:
        # Plain unsolicited message — remind owner how to use the bot
        await message.answer(
            "💡 To reply to a user, <b>swipe/reply</b> to their forwarded message.\n\n"
            "Owner commands:\n"
            "/stats — user count\n"
            "/broadcast — send announcement to all users",
            parse_mode="HTML",
        )
        return

    try:
        success = await route_reply_to_user(bot, message)
        if success:
            await message.answer("✅ Reply delivered.")
        else:
            await message.answer(
                "⚠️ Could not find the user for that message. "
                "The mapping may have expired or the message wasn't forwarded by this bot."
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to route owner reply: %s", exc)
        await message.answer("❌ Failed to deliver reply. Check logs.")
