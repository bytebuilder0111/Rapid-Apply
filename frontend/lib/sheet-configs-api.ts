import { api } from "@/lib/api";

export type SheetConfig = {
  profile_id: string;
  profile_name: string;
  enabled: boolean;
  spreadsheet_id: string | null;
  sheet_name: string | null;
};

export type SaveSheetConfigInput = {
  enabled: boolean;
  spreadsheet?: string | null;
  sheet_name?: string | null;
};

export const sheetConfigsApi = {
  list: () => api.get<SheetConfig[]>("/sheet-configs"),
  save: (profileId: string, input: SaveSheetConfigInput) =>
    api.put<SheetConfig>(`/sheet-configs/${profileId}`, input),
  tabs: (spreadsheet: string) =>
    api.get<{ tabs: string[] }>(`/sheet-configs/tabs?spreadsheet=${encodeURIComponent(spreadsheet)}`),
  test: (input: { spreadsheet: string; sheet_name: string }) =>
    api.post<void>("/sheet-configs/test", input),
};
