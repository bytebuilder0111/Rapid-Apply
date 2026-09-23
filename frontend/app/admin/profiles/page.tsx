"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { adminApi } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { profilesApi } from "@/lib/profiles-api";
import type { Profile } from "@/lib/types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function ProfileRow({ profile, clientName }: { profile: Profile; clientName: string }) {
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);

  const remove = useMutation({
    mutationFn: () => profilesApi.remove(profile.id),
    onSuccess: async () => {
      toast.success("Profile deleted");
      setDeleteOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["admin", "profiles"] });
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete profile")),
  });

  return (
    <TableRow>
      <TableCell className="font-medium">{profile.name}</TableCell>
      <TableCell>{clientName}</TableCell>
      <TableCell className="space-x-1">
        {profile.tech_stacks.map((s) => (
          <Badge key={s}>{s}</Badge>
        ))}
      </TableCell>
      <TableCell>
        {profile.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Inactive</Badge>}
      </TableCell>
      <TableCell className="text-right">
        <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
          Delete
        </Button>
      </TableCell>

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

export default function AdminProfilesPage() {
  const [clientId, setClientId] = useState<string>("");
  const { data: clients } = useQuery({
    queryKey: ["admin", "clients"],
    queryFn: () => adminApi.listClients(),
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "profiles", clientId],
    queryFn: () => profilesApi.list(clientId),
    enabled: Boolean(clientId),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Profiles</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        View and manage resume profiles across clients.
      </p>

      <div className="mt-4 max-w-xs">
        <Select value={clientId} onValueChange={(value) => setClientId(value ?? "")}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select a client" />
          </SelectTrigger>
          <SelectContent>
            {(clients ?? []).map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name} ({c.email})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mt-6 rounded-lg border">
        {!clientId && (
          <p className="p-4 text-sm text-muted-foreground">Pick a client to view its profiles.</p>
        )}
        {clientId && isLoading && <Skeleton className="m-4 h-32" />}
        {clientId && isError && (
          <p className="p-4 text-sm text-destructive">Couldn&apos;t load profiles.</p>
        )}
        {clientId && data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Tech Stacks</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No profiles for this client.
                  </TableCell>
                </TableRow>
              )}
              {data.map((p) => (
                <ProfileRow
                  key={p.id}
                  profile={p}
                  clientName={clients?.find((c) => c.id === clientId)?.name ?? ""}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
