"""Duplicate-job matching. A job counts as already recorded when its job link, or its company
name + position name, matches an earlier entry (a bid-sheet row or a saved analysis)."""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# Tracking parameters that differ between copies of the same posting link.
_TRACKING_PREFIXES = ("utm_", "ref=", "source=", "src=", "gh_src=", "trk=", "lever-source")


@dataclass
class Entry:
    company: str
    position: str
    job_link: str
    where: str  # e.g. "row 12 of Bid Sheet - ALL > Donzell-Auto"


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def normalize_link(url: str | None) -> str:
    """Same posting, same key: ignores scheme, "www.", trailing "/", #fragment, letter case in
    the host, and tracking parameters."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw if "://" in raw else "https://" + raw)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    params = sorted(
        p for p in parts.query.split("&") if p and not p.lower().startswith(_TRACKING_PREFIXES)
    )
    return host + path + ("?" + "&".join(params) if params else "")


def find_duplicate(
    entries: list[Entry], *, company: str, position: str, job_link: str
) -> str | None:
    """A user-facing reason if this job was already recorded, else None."""
    link = normalize_link(job_link)
    key = (normalize_text(company), normalize_text(position))
    for entry in entries:
        if link and normalize_link(entry.job_link) == link:
            return f"This job link is already recorded ({entry.where})."
    if all(key):
        for entry in entries:
            if (normalize_text(entry.company), normalize_text(entry.position)) == key:
                return (
                    f'"{company.strip()}" / "{position.strip()}" is already recorded '
                    f"({entry.where})."
                )
    return None
