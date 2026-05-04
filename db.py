"""
db.py — MongoDB connection, collection accessors, and index bootstrap.

Design decisions
----------------
* A single MongoClient is reused across the process (connection pooling).
* Indexes are created with create_index(..., background=True) so they
  don't block startup on large collections.
* All public helpers return plain Python dicts so callers never touch
  pymongo internals directly.
"""

import logging
from datetime import datetime, timezone

import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

import config

logger = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────
_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return (and lazily create) the shared MongoClient."""
    global _client
    if _client is None:
        _client = MongoClient(
            config.MONGO_URI,
            serverSelectionTimeoutMS=5_000,   # fail fast on bad URI
            connectTimeoutMS=5_000,
            socketTimeoutMS=10_000,
        )
    return _client


def get_db():
    """Return the application database handle."""
    return get_client()[config.MONGO_DB_NAME]


# ── Collection helpers ────────────────────────────────────────────────────────

def users_col():
    return get_db()["users"]


def messages_col():
    return get_db()["messages"]


# ── Index bootstrap ───────────────────────────────────────────────────────────

def ensure_indexes() -> None:
    """
    Create indexes on first run (idempotent — safe to call repeatedly).

    users       → unique index on user_id
    messages    → index on forwarded_message_id (lookup by Telegram msg ID)
                  index on user_id              (lookup all msgs from a user)
    """
    try:
        # users
        users_col().create_index(
            [("user_id", pymongo.ASCENDING)],
            unique=True,
            background=True,
            name="idx_users_user_id",
        )

        # messages — the hot path: owner replies → look up forwarded_message_id
        messages_col().create_index(
            [("forwarded_message_id", pymongo.ASCENDING)],
            background=True,
            name="idx_messages_fwd_msg_id",
        )
        messages_col().create_index(
            [("user_id", pymongo.ASCENDING)],
            background=True,
            name="idx_messages_user_id",
        )

        logger.info("MongoDB indexes verified / created.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to ensure indexes: %s", exc)
        raise


# ── Health check ─────────────────────────────────────────────────────────────

def ping() -> bool:
    """Return True if MongoDB is reachable."""
    try:
        get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("MongoDB ping failed: %s", exc)
        return False


# ── User helpers ──────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str | None) -> None:
    """
    Insert a new user document or touch `last_seen` on an existing one.
    `username` may be None for users without a public handle.
    """
    users_col().update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "username": username,
                "created_at": datetime.now(timezone.utc),
            },
            "$set": {
                "last_seen": datetime.now(timezone.utc),
                "username": username,   # keep username fresh
            },
        },
        upsert=True,
    )


def get_all_user_ids() -> list[int]:
    """Return every known user_id (for /broadcast)."""
    return [doc["user_id"] for doc in users_col().find({}, {"user_id": 1})]


def count_users() -> int:
    return users_col().count_documents({})


# ── Message-mapping helpers ───────────────────────────────────────────────────

def save_message_mapping(
    forwarded_message_id: int,
    user_id: int,
    original_message_id: int,
) -> None:
    """
    Persist the link between the owner's copy of a message and the
    originating user so we can route replies back.

    forwarded_message_id : Telegram message ID *in the owner's chat*
    user_id              : Telegram user ID of the sender
    original_message_id  : Telegram message ID *in the user's chat*
    """
    messages_col().insert_one(
        {
            "forwarded_message_id": forwarded_message_id,
            "user_id": user_id,
            "original_message_id": original_message_id,
            "timestamp": datetime.now(timezone.utc),
        }
    )


def get_user_id_by_forwarded(forwarded_message_id: int) -> int | None:
    """
    Given the message ID visible to the owner, return the originating
    user_id (or None if no mapping exists).
    """
    doc = messages_col().find_one(
        {"forwarded_message_id": forwarded_message_id},
        {"user_id": 1},
    )
    return doc["user_id"] if doc else None
