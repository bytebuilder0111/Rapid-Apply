"""Single writer class for Google Sheets (see CLAUDE.md: "one writer class under app/sheets/").

Adding Notion or Airtable later means a new class here, not touching app/sheets/service.py's
callers, which only depend on list_spreadsheets/get_spreadsheet/ensure_header/append_row.
"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.integrations.google_service import SCOPES

TOKEN_URI = "https://oauth2.googleapis.com/token"
SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"
MAX_SPREADSHEETS = 200

HEADER_ROW = [
    "Date",
    "Company",
    "Position",
    "Job Link",
    "Main Backend Skill",
    "Framework",
    "Secondary Skills",
    "Seniority",
    "Resume Used",
    "Recorded By",
    "Confidence",
]


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
            .get(spreadsheetId=spreadsheet_id, range=_a1(sheet_name, "A1:K1"))
            .execute()
        )
        if not existing.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=_a1(sheet_name, "A1"),
                valueInputOption="RAW",
                body={"values": [HEADER_ROW]},
            ).execute()

    def append_row(self, spreadsheet_id: str, sheet_name: str, row: list[str]) -> None:
        self._sheets().spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=_a1(sheet_name, "A1"),
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
