import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalysisResult } from "@/lib/analysis-api";

const SENIORITY_LABEL: Record<AnalysisResult["seniority"], string> = {
  junior: "Junior",
  mid: "Mid-level",
  senior: "Senior",
  lead: "Lead",
  unknown: "Unknown",
};

export function ResultCard({
  result,
  recommendedProfileName,
}: {
  result: AnalysisResult;
  recommendedProfileName: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Analysis result</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{result.main_backend_skill}</Badge>
          {result.backend_framework && <Badge variant="secondary">{result.backend_framework}</Badge>}
          <Badge variant="secondary">{SENIORITY_LABEL[result.seniority]}</Badge>
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

        <div className="rounded-md border p-3">
          <p className="text-sm font-medium text-muted-foreground">Recommended profile</p>
          <p className="mt-1 text-sm">
            {recommendedProfileName ?? (
              <span className="text-muted-foreground">No confident match</span>
            )}
            {recommendedProfileName && (
              <span className="ml-2 text-xs text-muted-foreground">
                {Math.round(result.confidence * 100)}% confidence
              </span>
            )}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{result.reasoning}</p>
        </div>
      </CardContent>
    </Card>
  );
}
