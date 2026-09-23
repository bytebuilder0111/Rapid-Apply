"use client";

import { useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useAuth } from "@/components/layout/auth-provider";
import { ResultCard } from "@/components/resume-selector/result-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { analysisApi, type AnalyzeOutput } from "@/lib/analysis-api";
import { ApiError } from "@/lib/api";
import { profilesApi } from "@/lib/profiles-api";

const formSchema = z.object({
  company_name: z.string().min(1, "Company name is required."),
  position_name: z.string().min(1, "Position name is required."),
  job_description: z.string().min(20, "Paste the full job description."),
  job_link: z.string().url("Enter a valid URL.").optional().or(z.literal("")),
});
type FormValues = z.infer<typeof formSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function ResumeSelector() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [analyzeOutput, setAnalyzeOutput] = useState<AnalyzeOutput | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");

  const { data: allProfiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profilesApi.list(),
  });

  // A bidder is limited to their one assigned profile; a client can pick any active one.
  const selectableProfiles = useMemo(() => {
    if (!allProfiles) return [];
    if (user?.role === "BIDDER") {
      return allProfiles.filter((p) => p.id === user.assigned_profile_id);
    }
    return allProfiles.filter((p) => p.is_active);
  }, [allProfiles, user]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting: isAnalyzing },
  } = useForm<FormValues>({ resolver: zodResolver(formSchema) });

  const onAnalyze = async (values: FormValues) => {
    try {
      const output = await analysisApi.analyze({
        company_name: values.company_name,
        position_name: values.position_name,
        job_description: values.job_description,
        job_link: values.job_link || null,
      });
      setAnalyzeOutput(output);
      setSelectedProfileId(output.result.recommended_profile_id ?? "");
      if (output.duplicate_warning) {
        toast.warning(output.duplicate_reason ?? "This job was already analyzed.");
      }
    } catch (error) {
      toast.error(errorMessage(error, "Analysis failed"));
    }
  };

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      if (!analyzeOutput) throw new Error("Analyze first");
      return analysisApi.save({
        company_name: values.company_name,
        position_name: values.position_name,
        job_description: values.job_description,
        job_link: values.job_link || null,
        selected_profile_id: selectedProfileId || null,
        result: analyzeOutput.result,
        model: analyzeOutput.model,
        prompt_version: analyzeOutput.prompt_version,
        tokens: analyzeOutput.tokens,
        latency_ms: analyzeOutput.latency_ms,
      });
    },
    onSuccess: async () => {
      toast.success("Analysis saved");
      setAnalyzeOutput(null);
      setSelectedProfileId("");
      reset();
      await queryClient.invalidateQueries({ queryKey: ["analyses"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't save analysis")),
  });

  const recommendedProfileName =
    selectableProfiles.find((p) => p.id === selectedProfileId)?.name ?? null;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Resume Selector</CardTitle>
          <CardDescription>
            Paste a job description to identify the main backend skill and the best-matching
            profile.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit(onAnalyze)}>
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
            <div className="flex flex-col gap-2">
              <Label htmlFor="job_link">Job link (optional)</Label>
              <Input id="job_link" placeholder="https://..." {...register("job_link")} />
              {errors.job_link && (
                <p className="text-sm text-destructive">{errors.job_link.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="job_description">Job description</Label>
              <Textarea id="job_description" rows={10} {...register("job_description")} />
              {errors.job_description && (
                <p className="text-sm text-destructive">{errors.job_description.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <Label>Profile</Label>
              <Select value={selectedProfileId} onValueChange={(v) => setSelectedProfileId(v ?? "")}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a profile" />
                </SelectTrigger>
                <SelectContent>
                  {selectableProfiles.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex gap-2">
              <Button type="submit" disabled={isAnalyzing}>
                {isAnalyzing ? "Analyzing..." : "Analyze"}
              </Button>
              {analyzeOutput && (
                <Button
                  type="button"
                  variant="outline"
                  disabled={save.isPending}
                  onClick={handleSubmit((values) => save.mutate(values))}
                >
                  {save.isPending ? "Saving..." : "Save"}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      <div>
        {analyzeOutput ? (
          <ResultCard result={analyzeOutput.result} recommendedProfileName={recommendedProfileName} />
        ) : (
          <Card className="flex h-full min-h-64 items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Results appear here after you analyze a job description.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
