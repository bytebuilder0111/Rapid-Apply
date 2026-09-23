"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { adminApi } from "@/lib/admin-api";
import type { RoleCounts } from "@/lib/types";

function CountCard({ title, counts }: { title: string; counts: RoleCounts }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-3xl font-semibold tracking-tight">{counts.total}</p>
        <p className="text-xs text-muted-foreground">
          {counts.last_7_days} in the last 7 days · {counts.last_30_days} in the last 30 days
        </p>
      </CardContent>
    </Card>
  );
}

export default function AdminDashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "dashboard"],
    queryFn: adminApi.dashboard,
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Overview of clients and bidders. Analysis counts land in Phase 6.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {isLoading && (
          <>
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </>
        )}
        {isError && (
          <p className="text-sm text-destructive">Couldn&apos;t load dashboard counts.</p>
        )}
        {data && (
          <>
            <CountCard title="Clients" counts={data.clients} />
            <CountCard title="Bidders" counts={data.bidders} />
          </>
        )}
      </div>
    </div>
  );
}
