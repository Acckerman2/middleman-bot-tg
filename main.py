"""
main.py — Entry point for the Telegram Middleman Bot.

Startup sequence
----------------
1. Validate configuration (config.py raises on missing vars).
2. Ping MongoDB and create indexes.
3. Build the aiogram Dispatcher and register routers.
4. Start long-polling (development) or webhook (production).

Router priority matters:
  owner router is checked first → its _is_owner filter rejects non-owners
  user router catches everything else (including unknown owner messages
  that didn't match any owner command).
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import db
from handlers import owner as owner_handlers
from handlers import user as user_handlers

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Bot & Dispatcher factory ──────────────────────────────────────────────────

def build_dispatcher() -> Dispatcher:
    """
    Create Dispatcher and attach routers in priority order.
    Owner router MUST be first so that /stats, /broadcast, and reply-routing
    are matched before the catch-all user handler.
    """
    dp = Dispatcher()
    dp.include_router(owner_handlers.router)   # 1 — owner-only (filtered)
    dp.include_router(user_handlers.router)    # 2 — all other users
    return dp


# ── Startup / shutdown hooks ──────────────────────────────────────────────────

async def on_startup(bot: Bot) -> None:
    logger.info("Starting Telegram Middleman Bot…")

    # Verify MongoDB is reachable before accepting updates
    if not db.ping():
        logger.critical("Cannot reach MongoDB — aborting startup.")
        sys.exit(1)

    db.ensure_indexes()

    me = await bot.get_me()
    logger.info("Logged in as @%s (id=%d)", me.username, me.id)
    logger.info("Owner ID: %d", config.OWNER_ID)

    # Notify owner that the bot is online
    try:
        await bot.send_message(
            config.OWNER_ID,
            "🟢 <b>Bot is online.</b>\n\n"
            "Commands:\n"
            "/stats — user count\n"
            "/broadcast &lt;text&gt; — send to all users\n\n"
            "Reply to any forwarded message to respond to that user.",
            parse_mode="HTML",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not notify owner on startup: %s", exc)


async def on_shutdown(bot: Bot) -> None:
    logger.info("Shutting down…")
    try:
        await bot.send_message(config.OWNER_ID, "🔴 Bot is going offline.")
    except Exception:  # noqa: BLE001
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Entering long-poll loop.")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
