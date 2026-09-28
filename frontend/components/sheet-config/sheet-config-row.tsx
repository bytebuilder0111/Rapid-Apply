"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/layout/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { integrationsApi } from "@/lib/integrations-api";
import { sheetConfigsApi, type SheetConfig } from "@/lib/sheet-configs-api";

const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm disabled:cursor-not-allowed disabled:opacity-50";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function SheetConfigRow({ config }: { config: SheetConfig }) {
  const queryClient = useQueryClient();
  const [spreadsheetId, setSpreadsheetId] = useState(config.spreadsheet_id ?? "");
  const [sheetName, setSheetName] = useState(config.sheet_name ?? "");

  useEffect(() => {
    setSpreadsheetId(config.spreadsheet_id ?? "");
    setSheetName(config.sheet_name ?? "");
  }, [config]);

  // Shared by every row: one "Load spreadsheets" click fills all dropdowns.
  const spreadsheets = useQuery({
    queryKey: ["google", "spreadsheets"],
    queryFn: sheetConfigsApi.spreadsheets,
    enabled: false,
    staleTime: 5 * 60 * 1000,
  });
  const listLoaded = spreadsheets.data !== undefined;

  // Tabs load once a spreadsheet is picked; the saved one's tab is shown without a Google call.
  const needTabs = Boolean(spreadsheetId) && (spreadsheetId !== config.spreadsheet_id || listLoaded);
  const tabs = useQuery({
    queryKey: ["google", "tabs", spreadsheetId],
    queryFn: () => sheetConfigsApi.tabs(spreadsheetId),
    enabled: needTabs,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    const first = tabs.data?.tabs[0];
    if (first && !tabs.data?.tabs.includes(sheetName)) setSheetName(first);
  }, [tabs.data, sheetName]);

  const spreadsheetOptions =
    spreadsheets.data ??
    (config.spreadsheet_id
      ? [{ id: config.spreadsheet_id, name: config.spreadsheet_name ?? config.spreadsheet_id }]
      : []);
  const tabOptions =
    tabs.data?.tabs ??
    (spreadsheetId === config.spreadsheet_id && config.sheet_name ? [config.sheet_name] : []);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["sheet-configs"] });

  const save = useMutation({
    mutationFn: () =>
      sheetConfigsApi.save(config.profile_id, { spreadsheet_id: spreadsheetId, sheet_name: sheetName }),
    onSuccess: async (saved) => {
      toast.success(`Saved: ${saved.spreadsheet_name} › ${saved.sheet_name}`);
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't save the sheet")),
  });

  const clear = useMutation({
    mutationFn: () => sheetConfigsApi.clear(config.profile_id),
    onSuccess: async () => {
      toast.success("Sheet cleared; this profile's analyses won't be recorded");
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't clear the sheet")),
  });

  const unchanged =
    config.enabled && spreadsheetId === config.spreadsheet_id && sheetName === config.sheet_name;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{config.profile_name}</CardTitle>
        <CardDescription>
          Every analysis saved for this profile, whichever resume it used, is added to this
          sheet as a new row.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm">
          Saved sheet:{" "}
          {config.enabled ? (
            <span className="font-semibold">
              {config.spreadsheet_name} › {config.sheet_name}
            </span>
          ) : (
            <span className="text-muted-foreground">Not set</span>
          )}
        </p>

        <div className="flex flex-col gap-2">
          <Label htmlFor={`sheet-${config.profile_id}`}>Spreadsheet</Label>
          <div className="flex gap-2">
            <select
              id={`sheet-${config.profile_id}`}
              className={SELECT_CLASS}
              value={spreadsheetId}
              onChange={(e) => setSpreadsheetId(e.target.value)}
              disabled={spreadsheetOptions.length === 0}
            >
              <option value="" disabled>
                {listLoaded ? "Choose a spreadsheet" : "Click Load spreadsheets"}
              </option>
              {spreadsheetOptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <Button
              type="button"
              variant="outline"
              className="shrink-0"
              disabled={spreadsheets.isFetching}
              onClick={async () => {
                const result = await spreadsheets.refetch();
                if (result.error) toast.error(errorMessage(result.error, "Couldn't load spreadsheets"));
                else if (result.data?.length === 0) toast.info("No spreadsheets found in this Google account");
              }}
            >
              {spreadsheets.isFetching && <Loader2 className="size-4 animate-spin" />}
              Load spreadsheets
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor={`tab-${config.profile_id}`}>Tab</Label>
          <select
            id={`tab-${config.profile_id}`}
            className={SELECT_CLASS}
            value={sheetName}
            onChange={(e) => setSheetName(e.target.value)}
            disabled={tabOptions.length === 0}
          >
            <option value="" disabled>
              {tabs.isFetching ? "Loading tabs..." : "Choose a spreadsheet first"}
            </option>
            {tabOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          {tabs.error && (
            <p className="text-sm text-destructive">
              {errorMessage(tabs.error, "Couldn't load this spreadsheet's tabs")}
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={!spreadsheetId || !sheetName || unchanged || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending && <Loader2 className="size-4 animate-spin" />}
            Save sheet
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!config.enabled || clear.isPending}
            onClick={() => clear.mutate()}
          >
            Clear sheet
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/** Google Sheet settings for the current user's profiles (all of a client's, or a
    bidder's one assigned profile). Requires the client's Google account to be connected. */
export function SheetConfigList() {
  const { user } = useAuth();
  const google = useQuery({
    queryKey: ["integrations", "google"],
    queryFn: integrationsApi.getGoogle,
  });
  const configs = useQuery({
    queryKey: ["sheet-configs"],
    queryFn: sheetConfigsApi.list,
    enabled: google.data?.connected === true,
  });

  if (google.isLoading) return <Skeleton className="h-40" />;
  if (google.isError) {
    return <p className="text-sm text-destructive">Couldn&apos;t check the Google connection.</p>;
  }

  if (!google.data?.connected) {
    return (
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle className="text-base">Connect Google first</CardTitle>
          <CardDescription>
            {user?.role === "CLIENT"
              ? "Sheet recording uses your Google account. Connect it under Integrations, then come back here to pick a spreadsheet from your Drive."
              : "Sheet recording uses your client's Google account, which isn't connected yet. Ask your client to connect it under Integrations."}
          </CardDescription>
        </CardHeader>
        {user?.role === "CLIENT" && (
          <CardContent>
            <Button nativeButton={false} render={<Link href="/client/integrations" />}>
              Go to Integrations
            </Button>
          </CardContent>
        )}
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Connected Google account: <span className="font-medium text-foreground">{google.data.email}</span>
        {google.data.status === "NEEDS_RECONNECT" && (
          <span className="text-destructive"> (needs reconnecting under Integrations)</span>
        )}
      </p>
      {configs.isLoading && <Skeleton className="h-40" />}
      {configs.isError && <p className="text-sm text-destructive">Couldn&apos;t load settings.</p>}
      {configs.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {user?.role === "CLIENT"
            ? "No active profiles yet. Create one under Resume Types first."
            : "You don't have an assigned profile yet."}
        </p>
      )}
      {configs.data?.map((config) => <SheetConfigRow key={config.profile_id} config={config} />)}
    </div>
  );
}
