"""Each user's session state (still active? which session version?), kept in memory for the
periodic "is my session still on?" check every open tab makes. Answering it from the database
kept Neon awake whenever any tab was open. The API runs as one process and every sign-out,
deactivation and password reset goes through it and clears this, so it stays exact; changes
made elsewhere (a script) show up within TTL."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

TTL = timedelta(minutes=10)

# user id -> (loaded at, can sign in, session version)
_cache: dict[UUID, tuple[datetime, bool, int]] = {}


def get(user_id: UUID) -> tuple[bool, int] | None:
    hit = _cache.get(user_id)
    if hit is None or datetime.now(UTC) - hit[0] > TTL:
        return None
    return hit[1], hit[2]


def put(user_id: UUID, *, usable: bool, session_version: int) -> None:
    _cache[user_id] = (datetime.now(UTC), usable, session_version)


def clear() -> None:
    """After any sign-out, deactivation or password reset has been committed."""
    _cache.clear()
