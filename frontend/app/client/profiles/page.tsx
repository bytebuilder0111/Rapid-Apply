"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { profilesApi } from "@/lib/profiles-api";
import type { Profile } from "@/lib/types";

const ACCEPT = ".pdf,.docx";
const MAX_BYTES = 5 * 1024 * 1024;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/** Returns an error message for a file the backend would reject, or null if it looks fine. */
function checkFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) return "Choose a .pdf or .docx file.";
  if (file.size > MAX_BYTES) return "Resume files must be 5 MB or smaller.";
  return null;
}

function NewResumeTypeDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const profile = await profilesApi.create({ name: name.trim() });
      try {
        return await profilesApi.uploadResume(profile.id, file as File);
      } catch (error) {
        // The resume type exists even if the upload failed; the card offers a retry.
        await queryClient.invalidateQueries({ queryKey: ["profiles"] });
        throw error;
      }
    },
    onSuccess: async () => {
      toast.success("Resume analyzed and saved");
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
      setName("");
      setFile(null);
      onOpenChange(false);
    },
    onError: (error) => setFormError(errorMessage(error, "Couldn't save this resume")),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setFormError("Name is required.");
    if (!file) return setFormError("Choose a resume file.");
    const fileError = checkFile(file);
    if (fileError) return setFormError(fileError);
    setFormError(null);
    create.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>New resume type</DialogTitle>
            <DialogDescription>
              Upload the resume for this type. The AI reads it once and keeps a short summary
              used to match job descriptions; the file itself isn&apos;t stored.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="e.g. Python Backend, iOS Mobile"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="resume">Resume (PDF or DOCX, max 5 MB)</Label>
              <Input
                id="resume"
                type="file"
                accept={ACCEPT}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            {formError && <p className="text-sm text-destructive">{formError}</p>}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="size-4 animate-spin" />}
              {create.isPending ? "Analyzing resume..." : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RenameDialog({
  profile,
  open,
  onOpenChange,
}: {
  profile: Profile;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(profile.name);

  const rename = useMutation({
    mutationFn: () => profilesApi.update(profile.id, { name: name.trim() }),
    onSuccess: async () => {
      toast.success("Renamed");
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
      onOpenChange(false);
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't rename")),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) rename.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Rename resume type</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={rename.isPending || !name.trim()}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResumeTypeCard({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["profiles"] });

  const upload = useMutation({
    mutationFn: (file: File) => profilesApi.uploadResume(profile.id, file),
    onSuccess: async () => {
      toast.success("Resume analyzed and saved");
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't upload resume")),
  });

  const toggleActive = useMutation({
    mutationFn: () => profilesApi.update(profile.id, { is_active: !profile.is_active }),
    onSuccess: invalidate,
    onError: (error) => toast.error(errorMessage(error, "Action failed")),
  });

  const remove = useMutation({
    mutationFn: () => profilesApi.remove(profile.id),
    onSuccess: async () => {
      toast.success("Resume type deleted");
      setDeleteOpen(false);
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete")),
  });

  const onFileChosen = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const fileError = checkFile(file);
    if (fileError) return toast.error(fileError);
    upload.mutate(file);
  };

  return (
    <Card className={profile.is_active ? undefined : "opacity-60"}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              {profile.name}
              {!profile.is_active && <Badge variant="secondary">Inactive</Badge>}
            </CardTitle>
            {profile.resume_filename && (
              <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                <FileText className="size-3" />
                {profile.resume_filename}
                {profile.resume_uploaded_at &&
                  ` · uploaded ${new Date(profile.resume_uploaded_at).toLocaleDateString()}`}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              className="hidden"
              onChange={onFileChosen}
            />
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => fileInput.current?.click()}
            >
              {upload.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Upload className="size-4" />
              )}
              {upload.isPending
                ? "Analyzing..."
                : profile.resume_summary
                  ? "Replace resume"
                  : "Upload resume"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setRenameOpen(true)}>
              Rename
            </Button>
            <Button variant="outline" size="sm" onClick={() => toggleActive.mutate()}>
              {profile.is_active ? "Deactivate" : "Activate"}
            </Button>
            <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {profile.resume_summary ? (
          <>
            <p className="text-sm leading-relaxed">{profile.resume_summary}</p>
            {profile.skills.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {profile.skills.map((s) => (
                  <Badge key={s} variant="secondary">
                    {s}
                  </Badge>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
            No resume uploaded yet. Upload a PDF or DOCX so this type can be matched to job
            descriptions.
          </p>
        )}
      </CardContent>

      <RenameDialog profile={profile} open={renameOpen} onOpenChange={setRenameOpen} />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {profile.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Bidders assigned to this resume type will be unassigned. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={remove.isPending} onClick={() => remove.mutate()}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

export default function ClientResumeTypesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profilesApi.list(),
  });

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Resume Types</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Each job description is compared against these resumes to pick the best fit.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>New resume type</Button>
      </div>

      <div className="mt-6 flex flex-col gap-4">
        {isLoading && <Skeleton className="h-32" />}
        {isError && <p className="text-sm text-destructive">Couldn&apos;t load resume types.</p>}
        {data?.length === 0 && (
          <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
            No resume types yet. Create one and upload its resume to start matching.
          </p>
        )}
        {data?.map((p) => <ResumeTypeCard key={p.id} profile={p} />)}
      </div>

      <NewResumeTypeDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
