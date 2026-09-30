"""Postgres connection pool (CLAUDE.MD §12).

The pool is created at startup and closed at shutdown. It is deliberately
optional: with no DATABASE_URL the app still serves /ws/audio and /api/health,
because the STT pipeline does not need a database and a missing DB must degrade
to "no case record", never to a dead socket.
"""

import logging

import asyncpg

from app.config import Settings

log = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def connect(settings: Settings) -> asyncpg.Pool | None:
    """Open the pool. Returns None if unconfigured or unreachable."""
    global _pool
    if not settings.database_url:
        log.info("DATABASE_URL unset — running without a case record")
        return None
    try:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
            # Render and Neon both idle sockets out; a stale connection would
            # otherwise surface as a failed tool call mid-demo.
            max_inactive_connection_lifetime=60.0,
            command_timeout=10.0,
        )
        async with _pool.acquire() as conn:
            await conn.execute("SELECT 1")
        log.info("Postgres pool ready")
    except Exception as exc:
        log.warning("Postgres unavailable: %s", exc)
        _pool = None
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool | None:
    return _pool


async def healthy() -> bool:
    """Round-trip the database. /api/health reports reachability, not config."""
    if _pool is None:
        return False
    try:
        async with _pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False
