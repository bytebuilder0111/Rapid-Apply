"use client";

import { useQuery } from "@tanstack/react-query";

import { SheetConfigRow } from "@/components/sheet-config/sheet-config-row";
import { Skeleton } from "@/components/ui/skeleton";
import { sheetConfigsApi } from "@/lib/sheet-configs-api";

export default function BidderConfigPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["sheet-configs"],
    queryFn: sheetConfigsApi.list,
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Config</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Personal Google Sheet auto-record for your assigned profile. When enabled, it&apos;s used
        instead of your client&apos;s profile-level sheet for your own analyses.
      </p>

      <div className="mt-6 flex flex-col gap-4 max-w-lg">
        {isLoading && <Skeleton className="h-40" />}
        {isError && <p className="text-sm text-destructive">Couldn&apos;t load config.</p>}
        {data?.map((config) => <SheetConfigRow key={config.profile_id} config={config} />)}
      </div>
    </div>
  );
}
