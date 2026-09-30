"""Single writer class for Google Sheets (see CLAUDE.md: "one writer class under app/sheets/").

Adding Notion or Airtable later means a new class here, not touching app/sheets/service.py's
callers, which only depend on list_spreadsheets/get_spreadsheet/ensure_header/
sheet_context/append_row.
"""

import threading

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.integrations.google_service import SCOPES

TOKEN_URI = "https://oauth2.googleapis.com/token"
SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"
MAX_SPREADSHEETS = 200

# The client's bid-sheet layout. Written only when a tab is empty; existing sheets keep their
# own header, and rows are appended in this column order.
HEADER_ROW = [
    "No",
    "Company Name",
    "Position Name",
    "Job Link",
    "Status",
    "Resume",
    "Date",
    "Job Description",
    "Applied By",
]
LAST_COLUMN = "I"


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _a1(sheet_name: str, cells: str) -> str:
    # Quote the tab name so names with spaces or punctuation ("Job Log") are valid ranges.
    return "'" + sheet_name.replace("'", "''") + "'!" + cells


# Credentials per refresh token, kept for the life of the process so the access token
# (valid ~1 hour, refreshed automatically when it expires) isn't fetched again on every call:
# each fetch is another round trip to Google.
_credentials_cache: dict[str, Credentials] = {}


def _credentials(refresh_token: str) -> Credentials:
    credentials = _credentials_cache.get(refresh_token)
    if credentials is None:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )
        _credentials_cache[refresh_token] = credentials
    return credentials


# Built API clients, kept per thread (an httplib2 connection mustn't be shared across
# threads). Building one and first touching its resources renders docs for every method:
# ~0.25s of CPU, several seconds on a small server, on every Google call if not reused.
_thread_clients = threading.local()


def _client(api: str, version: str, refresh_token: str):
    clients = _thread_clients.__dict__.setdefault("clients", {})
    key = (api, refresh_token)
    if key not in clients:
        clients[key] = build(
            api, version, credentials=_credentials(refresh_token), cache_discovery=False
        )
    return clients[key]


def _cell_text(value: object) -> str:
    """An unformatted cell as text: 12 rather than 12.0 for whole numbers."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class SheetsWriter:
    def __init__(self, refresh_token: str) -> None:
        self._refresh_token = refresh_token

    def _sheets(self):
        return _client("sheets", "v4", self._refresh_token)

    def list_spreadsheets(self) -> list[dict]:
        """[{"id", "name"}] for the account's spreadsheets, most recently modified first."""
        drive = _client("drive", "v3", self._refresh_token)
        result = (
            drive.files()
            .list(
                q=f"mimeType='{SPREADSHEET_MIME}' and trashed=false",
                fields="files(id,name)",
                orderBy="modifiedTime desc",
                pageSize=MAX_SPREADSHEETS,
            )
            .execute()
        )
        return [{"id": f["id"], "name": f["name"]} for f in result.get("files", [])]

    def get_spreadsheet(self, spreadsheet_id: str) -> tuple[str, list[str]]:
        """(title, tab names)."""
        meta = (
            self._sheets()
            .spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="properties.title,sheets.properties.title")
            .execute()
        )
        tabs = [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]
        return meta["properties"]["title"], tabs

    def ensure_header(self, spreadsheet_id: str, sheet_name: str) -> None:
        service = self._sheets()
        existing = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=_a1(sheet_name, f"A1:{LAST_COLUMN}1"))
            .execute()
        )
        if not existing.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=_a1(sheet_name, "A1"),
                valueInputOption="RAW",
                body={"values": [HEADER_ROW]},
            ).execute()

    def sheet_context(self, spreadsheet_id: str, sheet_name: str) -> tuple[int, str, str]:
        """(next "No" value, spreadsheet time zone, spreadsheet locale), in one request: the
        spreadsheet's settings together with column A's values."""
        result = (
            self._sheets()
            .spreadsheets()
            .get(
                spreadsheetId=spreadsheet_id,
                ranges=[_a1(sheet_name, "A:A")],
                includeGridData=True,
                fields="properties(timeZone,locale),sheets(data(rowData(values(effectiveValue))))",
            )
            .execute()
        )
        props = result["properties"]
        data = result.get("sheets", [{}])[0].get("data", [{}])[0]
        cells = [
            (row.get("values") or [{}])[0].get("effectiveValue", {})
            for row in data.get("rowData", [])
        ]
        if not any(cells):
            # A tab emptied since it was set up: put the header back before the first row.
            self.ensure_header(spreadsheet_id, sheet_name)
        numbers = [int(c["numberValue"]) for c in cells if "numberValue" in c]
        numbers += [
            int(float(c["stringValue"])) for c in cells if _is_number(c.get("stringValue", ""))
        ]
        return (max(numbers) + 1 if numbers else 1), props["timeZone"], props["locale"]

    def recorded_jobs(self, spreadsheet_id: str, sheet_name: str) -> list[tuple[int, list]]:
        """(sheet row number, [company, position, job link, date]) for every data row, from
        columns B-D and G of the bid-sheet layout (row 1 is the header). Values are read
        unformatted, so a date is its serial number whatever the cell's display format."""
        rows = (
            self._sheets()
            .spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=_a1(sheet_name, "B2:G"),
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="SERIAL_NUMBER",
            )
            .execute()
            .get("values", [])
        )
        jobs = []
        for i, row in enumerate(rows):
            cells = (row + [""] * 6)[:6]
            company, position, link = (_cell_text(v) for v in cells[:3])
            if company or position or link:
                jobs.append((i + 2, [company, position, link, cells[5]]))
        return jobs

    def append_row(self, spreadsheet_id: str, sheet_name: str, row: list) -> None:
        # USER_ENTERED so the link becomes clickable and the date a real date; callers escape
        # free text so it can't be read as a formula.
        self._sheets().spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=_a1(sheet_name, "A1"),
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
