"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { sheetConfigsApi, type SheetConfig } from "@/lib/sheet-configs-api";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

type Draft = {
  enabled: boolean;
  spreadsheet: string;
  sheet_name: string;
};

function draftFrom(config: SheetConfig): Draft {
  return {
    enabled: config.enabled,
    spreadsheet: config.spreadsheet_id ?? "",
    sheet_name: config.sheet_name ?? "",
  };
}

export function SheetConfigRow({ config }: { config: SheetConfig }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => draftFrom(config));
  const [tabs, setTabs] = useState<string[]>([]);

  useEffect(() => setDraft(draftFrom(config)), [config]);

  const loadTabs = useMutation({
    mutationFn: () => sheetConfigsApi.tabs(draft.spreadsheet),
    onSuccess: (data) => {
      setTabs(data.tabs);
      const firstTab = data.tabs[0];
      if (firstTab && !data.tabs.includes(draft.sheet_name)) {
        setDraft((d) => ({ ...d, sheet_name: firstTab }));
      }
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't load tabs")),
  });

  const testWrite = useMutation({
    mutationFn: () =>
      sheetConfigsApi.test({ spreadsheet: draft.spreadsheet, sheet_name: draft.sheet_name }),
    onSuccess: () => toast.success("Write access confirmed"),
    onError: (error) => toast.error(errorMessage(error, "Test failed")),
  });

  const save = useMutation({
    mutationFn: () =>
      sheetConfigsApi.save(config.profile_id, {
        enabled: draft.enabled,
        spreadsheet: draft.spreadsheet || null,
        sheet_name: draft.sheet_name || null,
      }),
    onSuccess: async () => {
      toast.success("Saved");
      await queryClient.invalidateQueries({ queryKey: ["sheet-configs"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't save")),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{config.profile_name}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <label className="flex items-center gap-2 text-sm font-medium">
          <Checkbox
            checked={draft.enabled}
            onCheckedChange={(value) => setDraft((d) => ({ ...d, enabled: value === true }))}
          />
          Auto record to Google Sheet
        </label>

        <div className="flex flex-col gap-2">
          <Label>Spreadsheet URL or ID</Label>
          <div className="flex gap-2">
            <Input
              placeholder="https://docs.google.com/spreadsheets/d/..."
              value={draft.spreadsheet}
              onChange={(e) => setDraft((d) => ({ ...d, spreadsheet: e.target.value }))}
            />
            <Button
              type="button"
              variant="outline"
              disabled={!draft.spreadsheet || loadTabs.isPending}
              onClick={() => loadTabs.mutate()}
            >
              {loadTabs.isPending ? "Loading..." : "Load tabs"}
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label>Sheet tab</Label>
          {tabs.length > 0 ? (
            <select
              className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
              value={draft.sheet_name}
              onChange={(e) => setDraft((d) => ({ ...d, sheet_name: e.target.value }))}
            >
              {tabs.map((tab) => (
                <option key={tab} value={tab}>
                  {tab}
                </option>
              ))}
            </select>
          ) : (
            <Input
              placeholder="Sheet1"
              value={draft.sheet_name}
              onChange={(e) => setDraft((d) => ({ ...d, sheet_name: e.target.value }))}
            />
          )}
        </div>

        <div className="flex gap-2">
          <Button type="button" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving..." : "Save"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!draft.spreadsheet || !draft.sheet_name || testWrite.isPending}
            onClick={() => testWrite.mutate()}
          >
            {testWrite.isPending ? "Testing..." : "Test"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
