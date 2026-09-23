"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ResultCard } from "@/components/resume-selector/result-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { analysisApi, type Analysis, type RecordStatus } from "@/lib/analysis-api";
import { profilesApi } from "@/lib/profiles-api";

const STATUS_VARIANT: Record<RecordStatus, "default" | "secondary" | "destructive"> = {
  SUCCESS: "default",
  PENDING: "secondary",
  SKIPPED: "secondary",
  FAILED: "destructive",
};

function ViewAnalysisDialog({
  analysis,
  open,
  onOpenChange,
  profileName,
}: {
  analysis: Analysis;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profileName: string | null;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {analysis.position_name} at {analysis.company_name}
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          {analysis.job_link && (
            <a
              href={analysis.job_link}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-primary underline"
            >
              Open job link
            </a>
          )}
          <ResultCard result={analysis.result} recommendedProfileName={profileName} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function AnalysisHistory() {
  const [search, setSearch] = useState("");
  const [profileId, setProfileId] = useState<string>("");
  const [viewing, setViewing] = useState<Analysis | null>(null);

  const { data: profiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profilesApi.list(),
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["analyses", search, profileId],
    queryFn: () => analysisApi.list({ search: search || undefined, profile_id: profileId || undefined }),
  });

  const profileNameById = useMemo(() => {
    const map = new Map<string, string>();
    (profiles ?? []).forEach((p) => map.set(p.id, p.name));
    return map;
  }, [profiles]);

  return (
    <div className="mt-8">
      <h2 className="text-xl font-semibold tracking-tight">History</h2>

      <div className="mt-3 flex flex-wrap gap-2">
        <Input
          placeholder="Search company or position..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={profileId} onValueChange={(v) => setProfileId(v ?? "")}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Filter by profile" />
          </SelectTrigger>
          <SelectContent>
            {(profiles ?? []).map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mt-4 rounded-lg border">
        {isLoading && <Skeleton className="m-4 h-32" />}
        {isError && <p className="p-4 text-sm text-destructive">Couldn&apos;t load history.</p>}
        {data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Position</TableHead>
                <TableHead>Profile</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No analyses yet.
                  </TableCell>
                </TableRow>
              )}
              {data.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{new Date(a.created_at).toLocaleDateString()}</TableCell>
                  <TableCell className="font-medium">{a.company_name}</TableCell>
                  <TableCell>{a.position_name}</TableCell>
                  <TableCell>
                    {a.selected_profile_id
                      ? (profileNameById.get(a.selected_profile_id) ?? "—")
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[a.record_status]}>{a.record_status}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" onClick={() => setViewing(a)}>
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {viewing && (
        <ViewAnalysisDialog
          analysis={viewing}
          open={Boolean(viewing)}
          onOpenChange={(open) => !open && setViewing(null)}
          profileName={
            viewing.selected_profile_id
              ? (profileNameById.get(viewing.selected_profile_id) ?? null)
              : null
          }
        />
      )}
    </div>
  );
}
