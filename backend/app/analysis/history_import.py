"""Imports a profile's past applications from a bid-sheet export (tab-separated, with the
header No | Company Name | Position Name | Job Link | ...  | Date) into job_history, so the
duplicate check knows about jobs applied to before this app existed.

    uv run python -m app.analysis.history_import --client Max \
        --profile "Lakeyth Terry" C:/Users/Administrator/Downloads/Lakeyth.txt

Re-importing the same file replaces that file's earlier rows instead of adding them twice.
"""

import argparse
import asyncio
import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.duplicates import parse_date
from app.analysis.models import JobHistory
from app.db import SessionLocal
from app.models import Role, User
from app.profiles.models import Profile

MAX_TEXT = 255


@dataclass
class HistoryRow:
    row_no: str
    company: str
    position: str
    job_link: str | None
    applied_on: date | None
    notes: list[str]


def _clean_link(value: str) -> str | None:
    """The first http(s) URL in the cell ("ehttps://..." typos included), or None."""
    match = re.search(r"https?://\S+", value)
    return match.group(0) if match else None


def _fit(value: str, label: str, notes: list[str]) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > MAX_TEXT:
        notes.append(f"{label} was {len(value)} characters; kept the first {MAX_TEXT}")
        value = value[:MAX_TEXT]
    return value


def parse_history(text: str) -> list[HistoryRow]:
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter="\t")
    header = [h.strip().lower() for h in next(reader, [])]
    try:
        col = {
            name: header.index(name)
            for name in ("no", "company name", "position name", "job link", "date")
        }
    except ValueError as exc:
        raise ValueError(f"Unexpected header {header}: {exc}") from exc

    rows: list[HistoryRow] = []
    for cells in reader:
        if not any(c.strip() for c in cells):
            continue
        cells += [""] * (len(header) - len(cells))
        notes: list[str] = []
        raw_link = cells[col["job link"]].strip()
        link = _clean_link(raw_link)
        if raw_link and link != raw_link:
            notes.append(f"job link {raw_link[:40]!r} " + ("fixed" if link else "is not a URL"))
        rows.append(
            HistoryRow(
                row_no=cells[col["no"]].strip(),
                company=_fit(cells[col["company name"]], "company", notes),
                position=_fit(cells[col["position name"]], "position", notes),
                job_link=link,
                applied_on=parse_date(cells[col["date"]]),
                notes=notes,
            )
        )
    return rows


async def import_history(
    db: AsyncSession, *, client_id: UUID, profile: Profile, rows: list[HistoryRow], file_name: str
) -> int:
    await db.execute(
        delete(JobHistory).where(
            JobHistory.profile_id == profile.id, JobHistory.source.like(f"{file_name} row %")
        )
    )
    db.add_all(
        JobHistory(
            client_id=client_id,
            profile_id=profile.id,
            company_name=r.company,
            position_name=r.position,
            job_link=r.job_link,
            applied_on=r.applied_on,
            source=f"{file_name} row {r.row_no}",
        )
        for r in rows
    )
    await db.commit()
    return len(rows)


async def _main(client_username: str, profile_name: str, path: Path) -> None:
    rows = parse_history(path.read_text(encoding="utf-8-sig"))
    async with SessionLocal() as db:
        client = (
            await db.execute(
                select(User).where(
                    func.lower(User.username) == client_username.lower(), User.role == Role.CLIENT
                )
            )
        ).scalar_one()
        profile = (
            await db.execute(
                select(Profile).where(Profile.client_id == client.id, Profile.name == profile_name)
            )
        ).scalar_one()
        count = await import_history(
            db, client_id=client.id, profile=profile, rows=rows, file_name=path.name
        )
    print(f"Imported {count} rows from {path.name} into {profile_name}'s history.")
    for r in rows:
        if r.notes:
            print(f"  row {r.row_no}: " + "; ".join(r.notes))
    no_date = [r.row_no for r in rows if r.applied_on is None]
    if no_date:
        print(f"  rows without a readable date: {', '.join(no_date)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client", required=True, help="the client's username")
    parser.add_argument("--profile", required=True, help='profile name, e.g. "Lakeyth Terry"')
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    asyncio.run(_main(args.client, args.profile, args.file))
