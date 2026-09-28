import { FileCheck2, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalysisResult, RoleType } from "@/lib/analysis-api";

const ROLE_LABEL: Record<RoleType, string> = {
  backend: "Backend",
  fullstack: "Full-stack",
  mobile: "Mobile",
  frontend: "Frontend",
  data: "Data",
  devops: "DevOps",
  other: "Other",
};

const SENIORITY_LABEL: Record<AnalysisResult["seniority"], string> = {
  intern: "Intern",
  junior: "Junior",
  mid: "Mid-level",
  senior: "Senior",
  lead: "Lead",
  unknown: "Seniority unknown",
};

function locationLabel(result: AnalysisResult): string | null {
  switch (result.work_arrangement) {
    case "remote":
      return result.remote_location === "us"
        ? "Remote · US"
        : result.remote_location === "worldwide"
          ? "Remote · anywhere"
          : result.remote_location === "non_us"
            ? "Remote · outside US"
            : "Remote";
    case "hybrid":
      return "Hybrid";
    case "onsite":
      return "On-site";
    default:
      return null;
  }
}

/** True when the AI compared this JD against resume summaries and none fit. */
export function isDismatched(result: AnalysisResult): boolean {
  return result.jd_summary !== undefined && !result.recommended_resume_type_id;
}

export function ResultCard({
  result,
  resumeName,
}: {
  result: AnalysisResult;
  /** Looks up a resume type's name by id (undefined if it was deleted). */
  resumeName: (id: string) => string | undefined;
}) {
  const bestName = result.recommended_resume_type_id
    ? (resumeName(result.recommended_resume_type_id) ?? "A deleted resume type")
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Analysis result</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {bestName ? (
          <div className="rounded-md border border-primary/40 bg-primary/5 p-3">
            <p className="text-sm font-medium text-muted-foreground">Best-fit resume</p>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-lg font-semibold">
              <FileCheck2 className="size-5 text-primary" />
              {bestName}
              <span className="text-sm font-normal text-muted-foreground">
                {Math.round(result.confidence * 100)}% fit
              </span>
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{result.reasoning}</p>
          </div>
        ) : result.skip_reason ? (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
            <p className="flex items-center gap-2 text-lg font-semibold text-destructive">
              <TriangleAlert className="size-5" />
              Skipped
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{result.skip_reason}</p>
          </div>
        ) : isDismatched(result) ? (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
            <p className="flex items-center gap-2 text-lg font-semibold text-destructive">
              <TriangleAlert className="size-5" />
              Dismatched JD
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{result.reasoning}</p>
          </div>
        ) : (
          <div className="rounded-md border p-3">
            <p className="text-sm font-medium text-muted-foreground">Recommended resume</p>
            <p className="mt-1 text-sm text-muted-foreground">No confident match</p>
            <p className="mt-1 text-sm text-muted-foreground">{result.reasoning}</p>
          </div>
        )}

        {result.jd_summary && (
          <div>
            <p className="text-sm font-medium text-muted-foreground">JD summary</p>
            <p className="mt-1 text-sm leading-relaxed">{result.jd_summary}</p>
          </div>
        )}

        <div>
          <p className="text-sm font-medium text-muted-foreground">Stack named in the JD</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {Array.isArray(result.jd_core_stack) ? (
              result.jd_core_stack.length > 0 ? (
                result.jd_core_stack.map((t) => <Badge key={t}>{t}</Badge>)
              ) : (
                <span className="text-sm text-muted-foreground">
                  No specific language or framework named
                </span>
              )
            ) : (
              <>
                <Badge>{result.main_backend_skill}</Badge>
                {result.backend_framework && <Badge>{result.backend_framework}</Badge>}
              </>
            )}
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-muted-foreground">Job details</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {result.role_type && (
              <Badge variant="outline">{ROLE_LABEL[result.role_type]} role</Badge>
            )}
            <Badge variant="outline">{SENIORITY_LABEL[result.seniority]}</Badge>
            {locationLabel(result) && <Badge variant="outline">{locationLabel(result)}</Badge>}
            {result.location_note && result.location_note.toLowerCase() !== "not stated" && (
              <span className="text-sm text-muted-foreground">{result.location_note}</span>
            )}
          </div>
          {result.work_arrangement === "unknown" && !result.skip_reason && (
            <p className="mt-2 rounded-md border border-yellow-500/40 bg-yellow-500/10 px-2 py-1 text-sm text-yellow-700 dark:text-yellow-300">
              Location not stated in the JD. Check it&apos;s a US remote role before applying.
            </p>
          )}
        </div>

        {result.secondary_skills.length > 0 && (
          <div>
            <p className="text-sm font-medium text-muted-foreground">Secondary skills</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {result.secondary_skills.map((s) => (
                <Badge key={s} variant="secondary">
                  {s}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {result.key_requirements.length > 0 && (
          <div>
            <p className="text-sm font-medium text-muted-foreground">Key requirements</p>
            <ul className="mt-1 list-disc pl-5 text-sm">
              {result.key_requirements.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
