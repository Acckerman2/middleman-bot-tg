"""
services/router.py — Core forwarding and reply-routing logic.

This layer sits between the handlers and Telegram/MongoDB so that
handler code stays thin and routing rules live in one place.

Key invariants
--------------
* The owner NEVER sees a raw user_id in the message UI.
  Identity is surfaced only via a short display string like
  "@username" or "User #4f2a" (last 4 hex chars of user_id).
* Every outbound forward to the owner is saved in MongoDB so that
  when the owner replies-to that message, we can route it back.
"""

import logging

from aiogram import Bot
from aiogram.types import Message

import db

logger = logging.getLogger(__name__)


def _user_display(message: Message) -> str:
    """
    Return a privacy-safe label for a user, e.g. '@alice' or 'User #3c9f'.
    Never exposes the numeric user_id.
    """
    user = message.from_user
    if user.username:
        return f"@{user.username}"
    # Deterministic short hash so the owner can distinguish multiple anon users
    short = format(user.id, "x")[-4:]
    return f"User #{short}"


async def forward_to_owner(bot: Bot, owner_id: int, message: Message) -> None:
    """
    Forward a user's message to the owner, prepending a header, and
    persist the forwarded_message_id → user_id mapping.

    Supports: text, photo, video, document, audio, voice, sticker.
    """
    user_id = message.from_user.id
    label = _user_display(message)
    header = f"📩 Message from {label}:\n"

    try:
        sent: Message | None = None

        if message.text:
            sent = await bot.send_message(
                owner_id,
                f"{header}{message.text}",
            )

        elif message.photo:
            # Telegram sends multiple resolutions; pick the largest.
            photo = message.photo[-1]
            sent = await bot.send_photo(
                owner_id,
                photo.file_id,
                caption=f"{header}{message.caption or ''}".strip(),
            )

        elif message.video:
            sent = await bot.send_video(
                owner_id,
                message.video.file_id,
                caption=f"{header}{message.caption or ''}".strip(),
            )

        elif message.document:
            sent = await bot.send_document(
                owner_id,
                message.document.file_id,
                caption=f"{header}{message.caption or ''}".strip(),
            )

        elif message.audio:
            sent = await bot.send_audio(
                owner_id,
                message.audio.file_id,
                caption=f"{header}{message.caption or ''}".strip(),
            )

        elif message.voice:
            sent = await bot.send_voice(
                owner_id,
                message.voice.file_id,
                caption=f"{header}{message.caption or ''}".strip(),
            )

        elif message.sticker:
            # Stickers don't support captions — send header separately
            await bot.send_message(owner_id, header.strip())
            sent = await bot.send_sticker(owner_id, message.sticker.file_id)

        else:
            # Unsupported type — notify owner as plain text
            sent = await bot.send_message(
                owner_id,
                f"{header}[Unsupported message type: {message.content_type}]",
            )

        if sent:
            db.save_message_mapping(
                forwarded_message_id=sent.message_id,
                user_id=user_id,
                original_message_id=message.message_id,
            )
            logger.info(
                "Forwarded msg %d from user %d → owner msg %d",
                message.message_id,
                user_id,
                sent.message_id,
            )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to forward message from user %d: %s",
            user_id,
            exc,
        )
        raise


async def route_reply_to_user(bot: Bot, owner_reply: Message) -> bool:
    """
    When the owner replies to a forwarded message, look up the original
    user and send the reply back.

    Returns True on success, False if no mapping was found.
    """
    if not owner_reply.reply_to_message:
        return False

    forwarded_id = owner_reply.reply_to_message.message_id
    user_id = db.get_user_id_by_forwarded(forwarded_id)

    if user_id is None:
        logger.warning(
            "No user mapping for forwarded_message_id=%d", forwarded_id
        )
        return False

    try:
        if owner_reply.text:
            await bot.send_message(user_id, owner_reply.text)

        elif owner_reply.photo:
            await bot.send_photo(
                user_id,
                owner_reply.photo[-1].file_id,
                caption=owner_reply.caption or "",
            )

        elif owner_reply.video:
            await bot.send_video(
                user_id,
                owner_reply.video.file_id,
                caption=owner_reply.caption or "",
            )

        elif owner_reply.document:
            await bot.send_document(
                user_id,
                owner_reply.document.file_id,
                caption=owner_reply.caption or "",
            )

        elif owner_reply.audio:
            await bot.send_audio(
                user_id,
                owner_reply.audio.file_id,
                caption=owner_reply.caption or "",
            )

        elif owner_reply.voice:
            await bot.send_voice(
                user_id,
                owner_reply.voice.file_id,
                caption=owner_reply.caption or "",
            )

        elif owner_reply.sticker:
            await bot.send_sticker(user_id, owner_reply.sticker.file_id)

        else:
            await bot.send_message(
                user_id,
                f"[Unsupported reply type: {owner_reply.content_type}]",
            )

        logger.info(
            "Routed owner reply (msg %d) → user %d",
            owner_reply.message_id,
            user_id,
        )
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to route reply to user %d: %s", user_id, exc)
        raise
