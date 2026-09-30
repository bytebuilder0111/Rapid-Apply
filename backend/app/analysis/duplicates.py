"""Duplicate-job matching. A job counts as already recorded when its job link, or its company
name + position name, matches an earlier entry (a bid-sheet row or a saved analysis). A job at a
company applied to within the last 7 days is also turned away, whatever the position."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

# Days after applying to a company before applying to it again (any position).
COMPANY_COOLDOWN_DAYS = 7

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
    applied_on: date | None = None


_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y")
# Google Sheets/Excel serial dates count days from 1899-12-30.
_SERIAL_EPOCH = date(1899, 12, 30)


def parse_date(value: object) -> date | None:
    """A bid-sheet date: a serial number (46294 or 46294.5), ISO or US text, else None."""
    if isinstance(value, int | float):
        return _SERIAL_EPOCH + timedelta(days=int(value)) if value > 0 else None
    text = str(value or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", text):
        return _SERIAL_EPOCH + timedelta(days=int(float(text)))
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_text(value: str | None) -> str:
    """Ignores case, possessive 's, punctuation and spacing, so "Mozilla,", "Samsara's"
    and "Prompt.io™" match "mozilla", "samsara" and "prompt io"."""
    text = (value or "").lower().replace("\u2019", "'")
    text = re.sub(r"'s\b", "", text)
    return re.sub(r"[^a-z0-9+#]+", " ", text).strip()


# Legal-form words that don't change which company it is ("Stripe, LLC" is "Stripe").
_COMPANY_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "gmbh", "plc"}


def normalize_company(value: str | None) -> str:
    words = normalize_text(value).split()
    while len(words) > 1 and words[-1] in _COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


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
    entries: list[Entry],
    *,
    company: str,
    position: str,
    job_link: str,
    today: date | None = None,
) -> str | None:
    """A user-facing reason if this job was already recorded, or its company was applied to
    within the last COMPANY_COOLDOWN_DAYS days (counting today); else None."""
    link = normalize_link(job_link)
    key = (normalize_company(company), normalize_text(position))
    for entry in entries:
        if link and normalize_link(entry.job_link) == link:
            return f"This job link is already recorded ({entry.where})."
    if all(key):
        for entry in entries:
            if (normalize_company(entry.company), normalize_text(entry.position)) == key:
                return (
                    f'"{company.strip()}" / "{position.strip()}" is already recorded '
                    f"({entry.where})."
                )
    if key[0] and today is not None:
        recent = [
            e
            for e in entries
            if e.applied_on is not None
            and 0 <= (today - e.applied_on).days < COMPANY_COOLDOWN_DAYS
            and normalize_company(e.company) == key[0]
        ]
        if recent:
            last = max(recent, key=lambda e: e.applied_on or date.min)
            assert last.applied_on is not None
            days = (today - last.applied_on).days
            when = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
            return (
                f'Already applied to "{last.company.strip()}" {when} '
                f'("{last.position.strip()}", {last.where}). Wait {COMPANY_COOLDOWN_DAYS} days '
                "before applying to the same company again."
            )
    return None
