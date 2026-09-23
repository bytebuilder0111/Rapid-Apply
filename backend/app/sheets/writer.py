"""Single writer class for Google Sheets (see CLAUDE.md: "one writer class under app/sheets/").

Adding Notion or Airtable later means a new class here, not touching app/sheets/service.py's
callers, which only depend on list_tabs/ensure_header/append_row.
"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

TOKEN_URI = "https://oauth2.googleapis.com/token"

HEADER_ROW = [
    "Date",
    "Company",
    "Position",
    "Job Link",
    "Main Backend Skill",
    "Framework",
    "Secondary Skills",
    "Seniority",
    "Profile Used",
    "Recorded By",
    "Confidence",
]


class SheetsWriter:
    def __init__(self, refresh_token: str) -> None:
        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
        )

    def _service(self):
        return build("sheets", "v4", credentials=self._credentials, cache_discovery=False)

    def list_tabs(self, spreadsheet_id: str) -> list[str]:
        meta = (
            self._service()
            .spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [sheet["properties"]["title"] for sheet in meta.get("sheets", [])]

    def ensure_header(self, spreadsheet_id: str, sheet_name: str) -> None:
        service = self._service()
        existing = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:K1")
            .execute()
        )
        if not existing.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": [HEADER_ROW]},
            ).execute()

    def append_row(self, spreadsheet_id: str, sheet_name: str, row: list[str]) -> None:
        self._service().spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
