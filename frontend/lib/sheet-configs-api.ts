import { api } from "@/lib/api";

export type SheetConfig = {
  profile_id: string;
  profile_name: string;
  /** True once a spreadsheet + tab is saved; analyses for this resume type then auto-record. */
  enabled: boolean;
  spreadsheet_id: string | null;
  spreadsheet_name: string | null;
  sheet_name: string | null;
};

export type Spreadsheet = { id: string; name: string };

export const sheetConfigsApi = {
  list: () => api.get<SheetConfig[]>("/sheet-configs"),
  spreadsheets: () => api.get<Spreadsheet[]>("/sheet-configs/spreadsheets"),
  tabs: (spreadsheetId: string) =>
    api.get<{ tabs: string[] }>(
      `/sheet-configs/tabs?spreadsheet_id=${encodeURIComponent(spreadsheetId)}`,
    ),
  save: (profileId: string, input: { spreadsheet_id: string; sheet_name: string }) =>
    api.put<SheetConfig>(`/sheet-configs/${profileId}`, input),
  clear: (profileId: string) => api.delete<SheetConfig>(`/sheet-configs/${profileId}`),
};
