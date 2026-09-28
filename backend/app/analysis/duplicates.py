"""Duplicate-job matching. A job counts as already recorded when its job link, or its company
name + position name, matches an earlier entry (a bid-sheet row or a saved analysis)."""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# Query parameters that differ between copies of the same posting link: tracking tags, and
# iCIMS page-layout parameters (width, mobile, ...).
_IGNORED_PARAMS = {
    "ref", "source", "src", "gh_src", "trk", "lever-source", "jr_id", "iis", "iisn",
    "jobsite", "mode", "mobile", "width", "height", "bga", "needsredirect", "jan1offset",
    "jun1offset", "hub", "codes",
}  # fmt: skip


@dataclass
class Entry:
    company: str
    position: str
    job_link: str
    where: str  # e.g. "row 12 of Bid Sheet - ALL > Donzell-Auto"


def normalize_text(value: str | None) -> str:
    """Ignores case, possessive 's, punctuation and spacing, so "Mozilla,", "Samsara's"
    and "Prompt.io™" match "mozilla", "samsara" and "prompt io"."""
    text = (value or "").lower().replace("\u2019", "'")
    text = re.sub(r"'s\b", "", text)
    return re.sub(r"[^a-z0-9+#]+", " ", text).strip()


def normalize_link(url: str | None) -> str:
    """Same posting, same key: ignores scheme, "www.", trailing "/", #fragment, letter case,
    tracking/layout parameters, and Greenhouse's embed form of a job link."""
    raw = (url or "").strip().lower()
    if not raw:
        return ""
    parts = urlsplit(raw if "://" in raw else "https://" + raw)
    host = parts.netloc.removeprefix("www.")
    path = parts.path.rstrip("/")
    params = {}
    for pair in parts.query.split("&"):
        name, _, value = pair.partition("=")
        if name and not name.startswith("utm_") and name not in _IGNORED_PARAMS:
            params[name] = value
    # job-boards.greenhouse.io/embed/job_app?for=acme&token=123 is job-boards.../acme/jobs/123
    if host.endswith("greenhouse.io") and path.startswith("/embed/job_app"):
        if "for" in params and "token" in params:
            path = f"/{params.pop('for')}/jobs/{params.pop('token')}"
            params.pop("gh_jid", None)
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return host + path + ("?" + query if query else "")


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
