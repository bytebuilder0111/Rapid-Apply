from uuid import UUID

from pydantic import BaseModel, Field


class SheetConfigOut(BaseModel):
    profile_id: UUID
    profile_name: str
    enabled: bool
    spreadsheet_id: str | None
    sheet_name: str | None


class SaveSheetConfigRequest(BaseModel):
    enabled: bool
    # Accepts either a bare spreadsheet ID or a full Google Sheets URL; the ID is
    # extracted server-side — see app/sheets/service.py:extract_spreadsheet_id.
    spreadsheet: str | None = None
    sheet_name: str | None = None


class TabsOut(BaseModel):
    tabs: list[str]


class TestWriteRequest(BaseModel):
    spreadsheet: str = Field(min_length=1)
    sheet_name: str = Field(min_length=1)
