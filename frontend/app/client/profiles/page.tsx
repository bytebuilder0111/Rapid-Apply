"use client";

import { useEffect, useRef, useState } from "react";
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
import { resumeTypesApi } from "@/lib/resume-types-api";
import type { Profile, ResumeType } from "@/lib/types";

const ACCEPT = ".pdf,.docx";
const MAX_BYTES = 5 * 1024 * 1024;
const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm sm:w-72";

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

/** Small "enter a name" dialog used for creating and renaming profiles and resume types. */
function NameDialog({
  open,
  onOpenChange,
  title,
  description,
  initialName = "",
  placeholder,
  submitLabel,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  initialName?: string;
  placeholder?: string;
  submitLabel: string;
  onSubmit: (name: string) => Promise<unknown>;
}) {
  const [name, setName] = useState(initialName);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) setName(initialName);
  }, [open, initialName]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setPending(true);
    try {
      await onSubmit(name.trim());
      onOpenChange(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't save"));
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <div className="py-4">
            <Input
              autoFocus
              placeholder={placeholder}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={pending || !name.trim()}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function NewResumeTypeDialog({
  profile,
  open,
  onOpenChange,
}: {
  profile: Profile;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const resumeType = await resumeTypesApi.create({ profile_id: profile.id, name: name.trim() });
      try {
        return await resumeTypesApi.uploadResume(resumeType.id, file as File);
      } catch (error) {
        // The resume type exists even if the upload failed; its card offers a retry.
        await queryClient.invalidateQueries({ queryKey: ["resume-types"] });
        throw error;
      }
    },
    onSuccess: async () => {
      toast.success("Resume analyzed and saved");
      await queryClient.invalidateQueries({ queryKey: ["resume-types"] });
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
            <DialogTitle>New resume type for {profile.name}</DialogTitle>
            <DialogDescription>
              Upload the resume for this type. The AI reads it once and keeps a short summary
              used to match job descriptions; the file itself isn&apos;t stored.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="rt-name">Name</Label>
              <Input
                id="rt-name"
                placeholder="e.g. Java, GoLang, Node"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="rt-file">Resume (PDF or DOCX, max 5 MB)</Label>
              <Input
                id="rt-file"
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

function ResumeTypeCard({ resumeType }: { resumeType: ResumeType }) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["resume-types"] });

  const upload = useMutation({
    mutationFn: (file: File) => resumeTypesApi.uploadResume(resumeType.id, file),
    onSuccess: async () => {
      toast.success("Resume analyzed and saved");
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't upload resume")),
  });

  const toggleActive = useMutation({
    mutationFn: () => resumeTypesApi.update(resumeType.id, { is_active: !resumeType.is_active }),
    onSuccess: invalidate,
    onError: (error) => toast.error(errorMessage(error, "Action failed")),
  });

  const remove = useMutation({
    mutationFn: () => resumeTypesApi.remove(resumeType.id),
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
    <Card className={resumeType.is_active ? undefined : "opacity-60"}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              {resumeType.name}
              {!resumeType.is_active && <Badge variant="secondary">Inactive</Badge>}
            </CardTitle>
            {resumeType.resume_filename && (
              <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                <FileText className="size-3" />
                {resumeType.resume_filename}
                {resumeType.resume_uploaded_at &&
                  ` · uploaded ${new Date(resumeType.resume_uploaded_at).toLocaleDateString()}`}
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
                : resumeType.resume_summary
                  ? "Replace resume"
                  : "Upload resume"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setRenameOpen(true)}>
              Rename
            </Button>
            <Button variant="outline" size="sm" onClick={() => toggleActive.mutate()}>
              {resumeType.is_active ? "Deactivate" : "Activate"}
            </Button>
            <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {resumeType.resume_summary ? (
          <>
            <p className="text-sm leading-relaxed">{resumeType.resume_summary}</p>
            {resumeType.skills.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {resumeType.skills.map((s) => (
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

      <NameDialog
        open={renameOpen}
        onOpenChange={setRenameOpen}
        title="Rename resume type"
        initialName={resumeType.name}
        submitLabel="Save"
        onSubmit={async (name) => {
          await resumeTypesApi.update(resumeType.id, { name });
          toast.success("Renamed");
          await invalidate();
        }}
      />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {resumeType.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its resume summary is removed. Past analyses keep their results. This can&apos;t be
              undone.
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
  const queryClient = useQueryClient();
  const [profileId, setProfileId] = useState("");
  const [newProfileOpen, setNewProfileOpen] = useState(false);
  const [renameProfileOpen, setRenameProfileOpen] = useState(false);
  const [deleteProfileOpen, setDeleteProfileOpen] = useState(false);
  const [newResumeOpen, setNewResumeOpen] = useState(false);

  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => profilesApi.list() });
  const resumeTypes = useQuery({
    queryKey: ["resume-types", profileId],
    queryFn: () => resumeTypesApi.list({ profileId }),
    enabled: Boolean(profileId),
  });

  // Keep a valid selection: default to the first profile, and recover if it's deleted.
  useEffect(() => {
    const list = profiles.data;
    if (list && !list.some((p) => p.id === profileId)) setProfileId(list[0]?.id ?? "");
  }, [profiles.data, profileId]);

  const selected = profiles.data?.find((p) => p.id === profileId);
  const refreshProfiles = () => queryClient.invalidateQueries({ queryKey: ["profiles"] });

  const deleteProfile = useMutation({
    mutationFn: () => profilesApi.remove(profileId),
    onSuccess: async () => {
      toast.success("Profile deleted");
      setDeleteProfileOpen(false);
      await refreshProfiles();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete profile")),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Resume Types</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Each profile has its own resumes. Job descriptions are matched against the chosen
        profile&apos;s resumes.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="profile-select">Profile</Label>
          <select
            id="profile-select"
            className={SELECT_CLASS}
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            disabled={!profiles.data?.length}
          >
            {!profiles.data?.length && <option value="">No profiles yet</option>}
            {profiles.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <Button variant="outline" onClick={() => setNewProfileOpen(true)}>
          New profile
        </Button>
        {selected && (
          <>
            <Button variant="outline" onClick={() => setRenameProfileOpen(true)}>
              Rename profile
            </Button>
            <Button variant="destructive" onClick={() => setDeleteProfileOpen(true)}>
              Delete profile
            </Button>
          </>
        )}
      </div>

      {profiles.isLoading && <Skeleton className="mt-6 h-32" />}
      {profiles.isError && (
        <p className="mt-6 text-sm text-destructive">Couldn&apos;t load profiles.</p>
      )}
      {profiles.data?.length === 0 && (
        <div className="mt-6 rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          <p>No profiles yet. A profile is the person you bid as, e.g. &quot;Lakeyth Terry&quot;.</p>
          <Button className="mt-3" onClick={() => setNewProfileOpen(true)}>
            Create a profile
          </Button>
        </div>
      )}

      {selected && (
        <div className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">{selected.name}&apos;s resume types</h2>
            <Button onClick={() => setNewResumeOpen(true)}>New resume type</Button>
          </div>
          <div className="mt-4 flex flex-col gap-4">
            {resumeTypes.isLoading && <Skeleton className="h-32" />}
            {resumeTypes.isError && (
              <p className="text-sm text-destructive">Couldn&apos;t load resume types.</p>
            )}
            {resumeTypes.data?.length === 0 && (
              <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
                No resume types for {selected.name} yet. Add one and upload its resume.
              </p>
            )}
            {resumeTypes.data?.map((rt) => <ResumeTypeCard key={rt.id} resumeType={rt} />)}
          </div>
          <NewResumeTypeDialog
            profile={selected}
            open={newResumeOpen}
            onOpenChange={setNewResumeOpen}
          />
        </div>
      )}

      <NameDialog
        open={newProfileOpen}
        onOpenChange={setNewProfileOpen}
        title="New profile"
        description="The person you bid as. Their resumes and Google Sheet are set up per profile."
        placeholder="e.g. Lakeyth Terry"
        submitLabel="Create"
        onSubmit={async (name) => {
          const created = await profilesApi.create({ name });
          toast.success(`Profile "${created.name}" created`);
          await refreshProfiles();
          setProfileId(created.id);
        }}
      />
      {selected && (
        <NameDialog
          open={renameProfileOpen}
          onOpenChange={setRenameProfileOpen}
          title="Rename profile"
          initialName={selected.name}
          submitLabel="Save"
          onSubmit={async (name) => {
            await profilesApi.update(selected.id, { name });
            toast.success("Profile renamed");
            await refreshProfiles();
          }}
        />
      )}
      <AlertDialog open={deleteProfileOpen} onOpenChange={setDeleteProfileOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete profile {selected?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This also deletes all of its resume types and its Google Sheet setting. Bidders
              assigned to it will be unassigned. Past analyses keep their results. This can&apos;t
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteProfile.isPending}
              onClick={() => deleteProfile.mutate()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
