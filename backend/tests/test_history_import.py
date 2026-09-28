from datetime import date

from app.analysis.history_import import MAX_TEXT, parse_history

HEADER = "No\tCompany Name\tPosition Name\tJob Link\tStatus\tResume Link\tDate\n"


def _parse(*lines: str):
    return parse_history(HEADER + "\n".join(lines) + "\n")


def test_parses_rows_and_every_date_format() -> None:
    rows = _parse(
        "1\tTuring\tSoftware Engineer\thttps://turing.betterteam.com/se-23\tApplied\tx\t"
        "9/4/2026 12:09:33",
        "2\tArtera\tSenior Engineer\thttps://jobs.lever.co/artera/cc5\tApplied\tx\t"
        "2026-09-07 18:44:28",
        "3\tBellese\tSenior Engineer\thttps://jobs.lever.co/bellese/58c\tApplied\tx\t46288.60641",
    )
    assert [(r.row_no, r.company, r.applied_on) for r in rows] == [
        ("1", "Turing", date(2026, 9, 4)),
        ("2", "Artera", date(2026, 9, 7)),
        ("3", "Bellese", date(2026, 9, 23)),
    ]
    assert all(not r.notes for r in rows)


def test_broken_links_are_fixed_or_dropped() -> None:
    fixed, dropped = _parse(
        "1\tMercury\tSenior SWE\tehttps://careers-mercury.icims.com/jobs/6772\tApplied\tx\t",
        "2\tSitusAMC\tFullstack Developer\tMcKesson\tApplied\tx\t",
    )
    assert fixed.job_link == "https://careers-mercury.icims.com/jobs/6772"
    assert dropped.job_link is None
    assert fixed.notes and dropped.notes


def test_oversized_cells_are_trimmed_and_noted() -> None:
    (row,) = _parse("1\tCookUnity\t" + "word " * 2000 + "\thttps://c.io/1\tApplied\tx\t")
    assert len(row.position) == MAX_TEXT
    assert "position was" in row.notes[0]
