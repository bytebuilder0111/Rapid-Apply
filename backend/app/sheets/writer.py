"""Single writer class for Google Sheets (see CLAUDE.md: "one writer class under app/sheets/").

Adding Notion or Airtable later means a new class here, not touching app/sheets/service.py's
callers, which only depend on list_spreadsheets/get_spreadsheet/ensure_header/
sheet_context/append_row.
"""

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
]
LAST_COLUMN = "H"


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _a1(sheet_name: str, cells: str) -> str:
    # Quote the tab name so names with spaces or punctuation ("Job Log") are valid ranges.
    return "'" + sheet_name.replace("'", "''") + "'!" + cells


class SheetsWriter:
    def __init__(self, refresh_token: str) -> None:
        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )

    def _sheets(self):
        return build("sheets", "v4", credentials=self._credentials, cache_discovery=False)

    def list_spreadsheets(self) -> list[dict]:
        """[{"id", "name"}] for the account's spreadsheets, most recently modified first."""
        drive = build("drive", "v3", credentials=self._credentials, cache_discovery=False)
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
        """(next "No" value, spreadsheet time zone, spreadsheet locale)."""
        service = self._sheets()
        props = (
            service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="properties(timeZone,locale)")
            .execute()["properties"]
        )
        column_a = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=_a1(sheet_name, "A:A"))
            .execute()
            .get("values", [])
        )
        numbers = [int(float(r[0])) for r in column_a if r and _is_number(r[0])]
        return (max(numbers) + 1 if numbers else 1), props["timeZone"], props["locale"]

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
