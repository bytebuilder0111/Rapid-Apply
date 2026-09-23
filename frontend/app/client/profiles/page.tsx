"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

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
import { Checkbox } from "@/components/ui/checkbox";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { profilesApi } from "@/lib/profiles-api";
import { techStacksApi } from "@/lib/tech-stacks-api";
import type { Profile } from "@/lib/types";

const profileSchema = z.object({
  name: z.string().min(1, "Name is required."),
  tech_stacks: z.array(z.string()).min(1, "Select at least one tech stack."),
});
type ProfileFormValues = z.infer<typeof profileSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function ProfileFormDialog({
  open,
  onOpenChange,
  profile,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profile?: Profile;
}) {
  const queryClient = useQueryClient();
  const isEdit = Boolean(profile);
  const { data: techStacks } = useQuery({
    queryKey: ["tech-stacks"],
    queryFn: techStacksApi.listActive,
  });
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    values: profile ? { name: profile.name, tech_stacks: profile.tech_stacks } : undefined,
  });

  const onSubmit = async (values: ProfileFormValues) => {
    // skills/notes aren't in this form: create defaults them ([]/null) on the backend,
    // and update omits them (exclude_unset) so any existing values are left untouched.
    try {
      if (isEdit && profile) {
        await profilesApi.update(profile.id, values);
        toast.success("Profile updated");
      } else {
        await profilesApi.create(values);
        toast.success("Profile created");
      }
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
      if (!isEdit) reset();
      onOpenChange(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't save profile"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit profile" : "New profile"}</DialogTitle>
            <DialogDescription>
              Used to match job descriptions and populate the AI recommendation context.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label>Tech Stacks</Label>
              <p className="text-xs text-muted-foreground">
                Select every stack this profile is strong in — JD analysis picks the best match.
              </p>
              <Controller
                control={control}
                name="tech_stacks"
                render={({ field }) => (
                  <div className="flex flex-col gap-2 rounded-md border p-3">
                    {(techStacks ?? []).map((stack) => {
                      const checked = field.value?.includes(stack.name) ?? false;
                      return (
                        <label
                          key={stack.id}
                          className="flex items-center gap-2 text-sm font-normal"
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={(value) => {
                              const current = field.value ?? [];
                              field.onChange(
                                value
                                  ? [...current, stack.name]
                                  : current.filter((name) => name !== stack.name),
                              );
                            }}
                          />
                          {stack.name}
                        </label>
                      );
                    })}
                    {(techStacks ?? []).length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No active tech stacks — ask an admin to add some.
                      </p>
                    )}
                  </div>
                )}
              />
              {errors.tech_stacks && (
                <p className="text-sm text-destructive">{errors.tech_stacks.message}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : isEdit ? "Save changes" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ProfileRow({ profile }: { profile: Profile }) {
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const toggleActive = useMutation({
    mutationFn: () => profilesApi.update(profile.id, { is_active: !profile.is_active }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Action failed")),
  });

  const remove = useMutation({
    mutationFn: () => profilesApi.remove(profile.id),
    onSuccess: async () => {
      toast.success("Profile deleted");
      setDeleteOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["profiles"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete profile")),
  });

  return (
    <TableRow>
      <TableCell className="font-medium">{profile.name}</TableCell>
      <TableCell className="space-x-1">
        {profile.tech_stacks.map((s) => (
          <Badge key={s}>{s}</Badge>
        ))}
      </TableCell>
      <TableCell>
        {profile.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Inactive</Badge>}
      </TableCell>
      <TableCell className="space-x-2 text-right">
        <Button variant="outline" size="sm" onClick={() => toggleActive.mutate()}>
          {profile.is_active ? "Deactivate" : "Activate"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
          Edit
        </Button>
        <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
          Delete
        </Button>
      </TableCell>

      <ProfileFormDialog open={editOpen} onOpenChange={setEditOpen} profile={profile} />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {profile.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Bidders currently assigned to this profile will be unassigned. This can&apos;t be
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
    </TableRow>
  );
}

export default function ClientProfilesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profilesApi.list(),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Profiles</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Resume profiles used to match job descriptions.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>New profile</Button>
      </div>

      <div className="mt-6 rounded-lg border">
        {isLoading && <Skeleton className="m-4 h-32" />}
        {isError && <p className="p-4 text-sm text-destructive">Couldn&apos;t load profiles.</p>}
        {data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Tech Stacks</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No profiles yet.
                  </TableCell>
                </TableRow>
              )}
              {data.map((p) => (
                <ProfileRow key={p.id} profile={p} />
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <ProfileFormDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
