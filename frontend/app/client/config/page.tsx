"use client";

import { useQuery } from "@tanstack/react-query";

import { SheetConfigRow } from "@/components/sheet-config/sheet-config-row";
import { Skeleton } from "@/components/ui/skeleton";
import { sheetConfigsApi } from "@/lib/sheet-configs-api";

export default function ClientConfigPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["sheet-configs"],
    queryFn: sheetConfigsApi.list,
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Config</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        For each profile, choose whether saved analyses auto-record to a Google Sheet.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        {isLoading && <Skeleton className="h-40" />}
        {isError && <p className="text-sm text-destructive">Couldn&apos;t load configs.</p>}
        {data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No active profiles yet. Create one under Profiles first.
          </p>
        )}
        {data?.map((config) => <SheetConfigRow key={config.profile_id} config={config} />)}
      </div>
    </div>
  );
}
