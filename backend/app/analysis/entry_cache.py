"""Each profile's earlier jobs (saved analyses + imported history), kept in memory for the
duplicate and cooldown checks. Re-reading them from the database for every job, three or four
times per Analyze/Save, was most of the app's database network transfer. The API runs as one
process, so updating the list on save keeps it exact; anything changed elsewhere (the history
import script, a manual fix) shows up within TTL."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.analysis.duplicates import Entry

TTL = timedelta(minutes=30)

_cache: dict[UUID, tuple[datetime, list[Entry]]] = {}


def get(profile_id: UUID) -> list[Entry] | None:
    hit = _cache.get(profile_id)
    if hit is None or datetime.now(UTC) - hit[0] > TTL:
        return None
    return list(hit[1])


def put(profile_id: UUID, entries: list[Entry]) -> None:
    _cache[profile_id] = (datetime.now(UTC), list(entries))


def add(profile_id: UUID, entry: Entry) -> None:
    """A job just saved: added to the profile's list if it's loaded."""
    if profile_id in _cache:
        _cache[profile_id][1].append(entry)


def forget(profile_id: UUID) -> None:
    _cache.pop(profile_id, None)
