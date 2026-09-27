from uuid import UUID

from pydantic import BaseModel, Field


class SheetConfigOut(BaseModel):
    profile_id: UUID
    profile_name: str
    enabled: bool
    spreadsheet_id: str | None
    spreadsheet_name: str | None
    sheet_name: str | None


class SaveSheetConfigRequest(BaseModel):
    """Saving a spreadsheet + tab turns auto-record on; clearing (DELETE) turns it off."""

    spreadsheet_id: str = Field(min_length=1)
    sheet_name: str = Field(min_length=1)


class SpreadsheetOut(BaseModel):
    id: str
    name: str


class TabsOut(BaseModel):
    tabs: list[str]
