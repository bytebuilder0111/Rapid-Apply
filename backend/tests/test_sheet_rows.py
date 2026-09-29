from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.sheets.service import _build_row, _sheet_date
from app.sheets.writer import HEADER_ROW, SheetsWriter

MOMENT = datetime(2026, 9, 4, 17, 9, 33, tzinfo=UTC)


def _analysis(**overrides) -> SimpleNamespace:
    base = {
        "company_name": "Turing",
        "position_name": "Software Engineer",
        "job_link": "https://turing.betterteam.com/software-engineer",
        "created_at": MOMENT,
        "job_description": "Build backend services in Node.js.",
    }
    return SimpleNamespace(**(base | overrides))


def test_header_matches_the_bid_sheet() -> None:
    assert HEADER_ROW == [
        "No",
        "Company Name",
        "Position Name",
        "Job Link",
        "Status",
        "Resume",
        "Date",
        "Job Description",
    ]


def test_row_follows_the_bid_sheet_columns() -> None:
    row = _build_row(
        _analysis(), number=2, resume_name="Node", time_zone="America/Chicago", locale="en_US"
    )
    assert row == [
        2,
        "Turing",
        "Software Engineer",
        "https://turing.betterteam.com/software-engineer",
        "Applied",
        "Node",
        "9/4/2026 12:09:33",  # 17:09 UTC is 12:09 in Chicago (CDT)
        "Build backend services in Node.js.",
    ]


def test_date_uses_the_spreadsheet_time_zone_and_locale() -> None:
    assert _sheet_date(MOMENT, "Asia/Tokyo", "en_US") == "9/5/2026 02:09:33"
    assert _sheet_date(MOMENT, "Europe/London", "en_GB") == "2026-09-04 18:09:33"
    assert _sheet_date(MOMENT, "Not/AZone", "en_US") == "9/4/2026 17:09:33"


def test_text_that_looks_like_a_formula_stays_text() -> None:
    row = _build_row(
        _analysis(company_name="=IMPORTXML(1)", job_link=None, job_description="+1 555"),
        number=1,
        resume_name="Java",
        time_zone="UTC",
        locale="en_US",
    )
    assert row[1] == "'=IMPORTXML(1)"
    assert row[3] == ""
    assert row[7] == "'+1 555"


def test_very_long_job_description_fits_in_a_cell() -> None:
    row = _build_row(
        _analysis(job_description="x" * 60_000),
        number=1,
        resume_name="Go",
        time_zone="UTC",
        locale="en_US",
    )
    assert len(row[7]) == 49_000


def _column_a(*cells: dict) -> dict:
    return {
        "properties": {"timeZone": "America/Chicago", "locale": "en_US"},
        "sheets": [{"data": [{"rowData": [{"values": [c]} if c else {} for c in cells]}]}],
    }


def test_next_number_continues_after_the_highest_no() -> None:
    writer = SheetsWriter.__new__(SheetsWriter)
    service = MagicMock()
    get = service.spreadsheets.return_value.get
    writer._sheets = lambda: service
    header = {"effectiveValue": {"stringValue": "No"}}

    # Numbers come back as numbers, or as text when typed with a leading apostrophe.
    get.return_value.execute.return_value = _column_a(
        header,
        {"effectiveValue": {"numberValue": 1}},
        {"effectiveValue": {"stringValue": "7"}},
        None,
        {"effectiveValue": {"numberValue": 3}},
    )
    assert writer.sheet_context("s1", "Bids") == (8, "America/Chicago", "en_US")
    assert get.call_count == 1  # settings and column A in one request

    get.return_value.execute.return_value = _column_a(header)
    assert writer.sheet_context("s1", "Bids")[0] == 1
