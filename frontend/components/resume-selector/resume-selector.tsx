"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, Loader2, TriangleAlert } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useAuth } from "@/components/layout/auth-provider";
import { isDismatched, ResultCard } from "@/components/resume-selector/result-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { analysisApi, type Analysis, type AnalyzeOutput } from "@/lib/analysis-api";
import { ApiError } from "@/lib/api";
import { profilesApi } from "@/lib/profiles-api";
import { resumeTypesApi } from "@/lib/resume-types-api";

const formSchema = z.object({
  company_name: z.string().min(1, "Company name is required."),
  position_name: z.string().min(1, "Position name is required."),
  job_description: z.string().min(20, "Paste the full job description."),
  job_link: z.string().min(1, "Job link is required.").url("Enter a valid URL."),
});
type FormValues = z.infer<typeof formSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/** The sheet write runs in the background after Save: show it in progress right away, then
 * replace that message with how it went. */
async function reportRecording(saved: Analysis, id: string | number): Promise<void> {
  const label = `${saved.company_name} / ${saved.position_name}`;
  let current = saved;
  for (let i = 0; i < 40 && current.record_status === "PENDING"; i++) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    current = await analysisApi.get(saved.id).catch(() => current);
  }
  if (current.record_status === "SUCCESS") {
    toast.success(`Recorded in the Google Sheet: ${label}`, { id });
  } else if (current.record_status === "SKIPPED") {
    toast.info(`Saved: ${label}. No Google Sheet is set for this profile, so it wasn't recorded.`, {
      id,
    });
  } else if (current.record_status === "FAILED") {
    toast.error(`Saved, but recording to the Google Sheet failed: ${current.record_error}`, {
      id,
      duration: 30000,
      action: {
        label: "Retry",
        onClick: async () => {
          try {
            const retried = await analysisApi.retry(saved.id);
            if (retried.record_status === "SUCCESS") toast.success("Recorded in the Google Sheet");
            else toast.error(`Still couldn't record it: ${retried.record_error}`);
          } catch (error) {
            toast.error(errorMessage(error, "Retry failed"));
          }
        },
      },
    });
  } else {
    toast.info(`Saved: ${label}. Still recording to the Google Sheet...`, { id });
  }
}

/** A job being recorded: captured at the click, since the form is cleared right away. */
type RecordJob = {
  values: FormValues;
  output: AnalyzeOutput;
  profileId: string;
  toastId: string | number;
};

// Seconds into the AI call; the AI's own progress isn't observable, so these are estimates.
const AI_STEPS = [
  { label: "AI is reading the job description", untilSec: 3 },
  { label: "Summarizing the job description", untilSec: 7 },
  { label: "Comparing with your resumes", untilSec: Infinity },
];
const STEP_LABELS = ["Checking for duplicates", ...AI_STEPS.map((step) => step.label)];
const EXPECTED_SECONDS = 15;
// A duplicate check normally takes ~1s; much longer means the free server is waking up.
const SLOW_CHECK_SECONDS = 5;

type AnalyzePhase = "checking" | "analyzing";

function AnalyzingPanel({ phase }: { phase: AnalyzePhase }) {
  const [started] = useState(() => Date.now());
  const [aiStarted, setAiStarted] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (phase === "analyzing") setAiStarted((t) => t ?? Date.now());
  }, [phase]);

  const elapsed = (now - started) / 1000;
  const aiElapsed = aiStarted ? Math.max(0, (now - aiStarted) / 1000) : 0;
  // Step 0 is real (the duplicate check); the AI steps follow the estimates above.
  const activeIndex =
    phase === "checking" ? 0 : 1 + AI_STEPS.findIndex((step) => aiElapsed < step.untilSec);
  // Ease toward 95% so it never looks stuck or done early.
  const percent =
    phase === "checking"
      ? 5
      : Math.min(95, 10 + Math.round((1 - Math.exp(-aiElapsed / (EXPECTED_SECONDS / 2))) * 85));
  const wakingUp = phase === "checking" && elapsed > SLOW_CHECK_SECONDS;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Loader2 className="size-4 animate-spin" />
          <span>{phase === "checking" ? "Checking for duplicates..." : "Analyzing..."}</span>
        </CardTitle>
        <CardDescription>
          {wakingUp
            ? `${Math.floor(elapsed)}s · the server is waking up after being idle, this can take up to a minute`
            : phase === "checking"
              ? `${Math.floor(elapsed)}s · the AI starts only if this job is new`
              : `${Math.floor(elapsed)}s elapsed · usually takes 5–20 seconds`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-200"
            style={{ width: `${percent}%` }}
          />
        </div>
        <ul className="flex flex-col gap-2 text-sm">
          {STEP_LABELS.map((label, i) => (
            <li
              key={label}
              className={i > activeIndex ? "flex items-center gap-2 text-muted-foreground" : "flex items-center gap-2"}
            >
              {i < activeIndex ? (
                <CheckCircle2 className="size-4 text-primary" />
              ) : i === activeIndex ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Circle className="size-4" />
              )}
              {label}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function ResumeSelector() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [analyzeOutput, setAnalyzeOutput] = useState<AnalyzeOutput | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [duplicateOf, setDuplicateOf] = useState<string | null>(null);
  // The analysis the user confirmed applying to; Record to Sheet shows only for that one.
  const [appliedTo, setAppliedTo] = useState<AnalyzeOutput | null>(null);
  const [phase, setPhase] = useState<AnalyzePhase>("checking");
  const isBidder = user?.role === "BIDDER";
  const [chosenProfileId, setChosenProfileId] = useState<string>("");
  const resultRef = useRef<HTMLDivElement>(null);

  const scrollToResult = () =>
    requestAnimationFrame(() =>
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );

  const { data: allProfiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profilesApi.list(),
  });
  const activeProfiles = useMemo(
    () => (allProfiles ?? []).filter((p) => p.is_active),
    [allProfiles],
  );

  // A bidder always works with their one assigned profile; a client picks one.
  const profileId = isBidder ? (user?.assigned_profile_id ?? "") : chosenProfileId;
  const profile = allProfiles?.find((p) => p.id === profileId);

  useEffect(() => {
    const first = activeProfiles[0];
    if (!isBidder && !chosenProfileId && first) setChosenProfileId(first.id);
  }, [isBidder, chosenProfileId, activeProfiles]);

  const { data: resumeTypes } = useQuery({
    queryKey: ["resume-types", profileId],
    queryFn: () => resumeTypesApi.list({ profileId }),
    enabled: Boolean(profileId),
  });

  const changeProfile = (id: string) => {
    setChosenProfileId(id);
    setAnalyzeOutput(null);
    setAnalyzeError(null);
    setDuplicateOf(null);
  };

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting: isAnalyzing },
  } = useForm<FormValues>({ resolver: zodResolver(formSchema) });

  const onAnalyze = async (values: FormValues) => {
    if (!profileId) {
      toast.error(isBidder ? "You have no assigned profile yet." : "Choose a profile first.");
      return;
    }
    setAnalyzeOutput(null);
    setAnalyzeError(null);
    setDuplicateOf(null);
    setPhase("checking");
    scrollToResult();
    try {
      // Duplicates are caught here, in about a second, before any AI time is spent.
      const { duplicate } = await analysisApi.checkDuplicate({
        company_name: values.company_name,
        position_name: values.position_name,
        job_link: values.job_link,
        profile_id: profileId,
      });
      if (duplicate) {
        setDuplicateOf(duplicate);
        toast.error(`Duplicate job: ${duplicate}`);
        scrollToResult();
        return;
      }
      setPhase("analyzing");
      const output = await analysisApi.analyze({
        company_name: values.company_name,
        position_name: values.position_name,
        job_description: values.job_description,
        job_link: values.job_link,
        profile_id: profileId,
      });
      setAnalyzeOutput(output);
      if (output.result.skip_reason) {
        toast.warning(`Skipped: ${output.result.skip_reason}`);
      } else if (isDismatched(output.result)) {
        toast.warning(`Dismatched JD: none of ${profile?.name ?? "this profile"}'s resumes fit this job.`);
      }
      scrollToResult();
    } catch (error) {
      const message = errorMessage(error, "Analysis failed. Please try again.");
      setAnalyzeError(message);
      toast.error(message);
      scrollToResult();
    }
  };

  const save = useMutation({
    mutationFn: ({ values, output, profileId }: RecordJob) =>
      analysisApi.save({
        company_name: values.company_name,
        position_name: values.position_name,
        job_description: values.job_description,
        job_link: values.job_link,
        profile_id: profileId,
        // The resume is the AI's pick; there's nothing to choose by hand.
        selected_resume_type_id: output.result.recommended_resume_type_id ?? null,
        result: output.result,
        model: output.model,
        prompt_version: output.prompt_version,
        tokens: output.tokens,
        latency_ms: output.latency_ms,
      }),
    onSuccess: async (saved, { toastId }) => {
      void reportRecording(saved, toastId);
      await queryClient.invalidateQueries({ queryKey: ["analyses"] });
    },
    // The form was already cleared; offer the job back so nothing is lost.
    onError: (error, { values, output, toastId }) =>
      toast.error(errorMessage(error, "Couldn't save analysis"), {
        id: toastId,
        duration: 30000,
        action: {
          label: "Restore",
          onClick: () => {
            reset(values);
            setAnalyzeOutput(output);
          },
        },
      }),
  });

  // Clears the form the moment the button is clicked; saving and the sheet write carry on
  // in the background, reported in one toast.
  const record = (values: FormValues) => {
    if (!analyzeOutput) return;
    const output = analyzeOutput;
    const toastId = toast.loading(
      `Recording to the Google Sheet: ${values.company_name} / ${values.position_name}...`,
    );
    setAnalyzeOutput(null);
    reset();
    save.mutate({ values, output, profileId, toastId });
  };

  const canConfirm = analyzeOutput !== null && !isDismatched(analyzeOutput.result);
  const applied = canConfirm && appliedTo === analyzeOutput;

  const resumeName = (id: string) => resumeTypes?.find((r) => r.id === id)?.name;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Resume Selector</CardTitle>
          <CardDescription>
            Paste a job description. The AI summarizes it and picks which of the profile&apos;s
            resumes fits best.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit(onAnalyze)}>
            <div className="flex flex-col gap-2">
              <Label htmlFor="profile">Profile</Label>
              {isBidder ? (
                <p className="text-sm font-medium">
                  {profile?.name ?? "No profile assigned yet. Ask your client to assign one."}
                </p>
              ) : (
                <select
                  id="profile"
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={chosenProfileId}
                  onChange={(e) => changeProfile(e.target.value)}
                  disabled={activeProfiles.length === 0}
                >
                  {activeProfiles.length === 0 && (
                    <option value="">No profiles yet: create one under Resume Types</option>
                  )}
                  {activeProfiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="company_name">Company name</Label>
                <Input id="company_name" {...register("company_name")} />
                {errors.company_name && (
                  <p className="text-sm text-destructive">{errors.company_name.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="position_name">Position name</Label>
                <Input id="position_name" {...register("position_name")} />
                {errors.position_name && (
                  <p className="text-sm text-destructive">{errors.position_name.message}</p>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="job_link">Job link</Label>
              <Input id="job_link" placeholder="https://..." {...register("job_link")} />
              {errors.job_link && (
                <p className="text-sm text-destructive">{errors.job_link.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="job_description">Job description</Label>
              <Textarea
                id="job_description"
                className="h-72 resize-none overflow-y-auto field-sizing-fixed"
                placeholder="Paste the full job description here..."
                {...register("job_description")}
              />
              {errors.job_description && (
                <p className="text-sm text-destructive">{errors.job_description.message}</p>
              )}
            </div>

            <div className="flex gap-2">
              <Button type="submit" disabled={isAnalyzing}>
                {isAnalyzing && <Loader2 className="size-4 animate-spin" />}
                <span>
                  {!isAnalyzing ? "Analyze" : phase === "checking" ? "Checking duplicates..." : "Analyzing..."}
                </span>
              </Button>
              {/* All three are always shown and unlock in order: a matched analysis enables the
                  question, and confirming it enables recording (only applied jobs are recorded). */}
              <Button
                type="button"
                variant="outline"
                disabled={!canConfirm || applied}
                onClick={() => setAppliedTo(analyzeOutput)}
              >
                {/* Text in its own span: page translators (Chrome Translate) replace bare text
                    nodes, and React then crashes inserting the icon next to them. */}
                {applied && <CheckCircle2 className="size-4" />}
                <span>Did you apply to this job?</span>
              </Button>
              <Button type="button" variant="outline" disabled={!applied} onClick={handleSubmit(record)}>
                Record to Sheet
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div ref={resultRef} className="scroll-mt-6 lg:sticky lg:top-6 lg:self-start">
        {isAnalyzing ? (
          <AnalyzingPanel phase={phase} />
        ) : duplicateOf ? (
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-destructive">
                <TriangleAlert className="size-4" />
                Duplicate job, not analyzed
              </CardTitle>
              <CardDescription>{duplicateOf}</CardDescription>
            </CardHeader>
          </Card>
        ) : analyzeOutput ? (
          <div className="flex flex-col gap-2">
            <ResultCard result={analyzeOutput.result} resumeName={resumeName} />
            <p className="text-xs text-muted-foreground">
              {analyzeOutput.result.skip_reason ? (
                <span key="skipped">A skipped job can&apos;t be saved.</span>
              ) : isDismatched(analyzeOutput.result) ? (
                <span key="dismatched">A Dismatched JD can&apos;t be saved.</span>
              ) : appliedTo === analyzeOutput ? (
                <span key="applied">
                  Not recorded yet: click <span className="font-medium">Record to Sheet</span> to add it to
                  the profile&apos;s Google Sheet.
                </span>
              ) : (
                <span key="not-applied">
                  Not recorded yet: once you&apos;ve applied, click{" "}
                  <span className="font-medium">Did you apply to this job?</span>
                </span>
              )}
            </p>
          </div>
        ) : analyzeError ? (
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-destructive">
                <TriangleAlert className="size-4" />
                Analysis failed
              </CardTitle>
              <CardDescription>{analyzeError}</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <Card className="flex min-h-64 items-center justify-center p-6">
            <p className="text-center text-sm text-muted-foreground">
              Results appear here after you click <span className="font-medium">Analyze</span>.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
