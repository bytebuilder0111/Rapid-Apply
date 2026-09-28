"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { BidderUser, ClientUser } from "@/lib/types";

const createSchema = z.object({
  username: z
    .string()
    .trim()
    .min(2, "Username must be at least 2 characters.")
    .max(50, "Username must be at most 50 characters.")
    .regex(/^[A-Za-z0-9._-]+$/, "Use letters, numbers, dots, dashes or underscores (no spaces)."),
  password: z.string().min(8, "At least 8 characters."),
  assigned_profile_id: z.string().min(1, "Pick a profile."),
});
type CreateValues = z.infer<typeof createSchema>;

const passwordSchema = z.object({ new_password: z.string().min(8, "At least 8 characters.") });
type PasswordValues = z.infer<typeof passwordSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function useClientOptions() {
  return useQuery({ queryKey: ["admin", "clients"], queryFn: () => adminApi.listClients() });
}

function CreateBidderDialog() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const { data: clients } = useClientOptions();
  const clientName = (id: string) => clients?.find((c: ClientUser) => c.id === id)?.name;
  const profileLabel = (p: { name: string; client_id: string }) =>
    clientName(p.client_id) ? `${p.name} (${clientName(p.client_id)})` : p.name;

  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({ resolver: zodResolver(createSchema) });

  // Every client's profiles; the bidder's client is the chosen profile's client.
  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ["profiles", "all"],
    queryFn: () => profilesApi.list(),
    enabled: open,
  });

  const onSubmit = async (values: CreateValues) => {
    try {
      await adminApi.createBidder(values);
      toast.success("Bidder created");
      await queryClient.invalidateQueries({ queryKey: ["admin", "bidders"] });
      reset();
      setOpen(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't create bidder"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>New bidder</Button>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>New bidder</DialogTitle>
            <DialogDescription>
              A bidder works under one profile, and belongs to that profile&apos;s client.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label>Assigned profile</Label>
              <Controller
                control={control}
                name="assigned_profile_id"
                render={({ field }) => (
                  <Select
                    value={field.value ?? null}
                    onValueChange={field.onChange}
                    items={Object.fromEntries((profiles ?? []).map((p) => [p.id, profileLabel(p)]))}
                    disabled={profilesLoading}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select a profile" />
                    </SelectTrigger>
                    <SelectContent>
                      {(profiles ?? [])
                        .filter((p) => p.is_active)
                        .map((p) => (
                          <SelectItem key={p.id} value={p.id}>
                            {profileLabel(p)}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {profiles?.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No profiles yet. A client creates them under Resume Types.
                </p>
              )}
              {errors.assigned_profile_id && (
                <p className="text-sm text-destructive">{errors.assigned_profile_id.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" autoComplete="off" {...register("username")} />
              {errors.username && <p className="text-sm text-destructive">{errors.username.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResetPasswordDialog({
  bidder,
  open,
  onOpenChange,
}: {
  bidder: BidderUser;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) });

  const onSubmit = async (values: PasswordValues) => {
    try {
      await adminApi.resetBidderPassword(bidder.id, values.new_password);
      toast.success(`Password reset for ${bidder.username}`);
      reset();
      onOpenChange(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't reset password"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>Sets a new password for {bidder.username}.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-4">
            <Label htmlFor="new_password">New password</Label>
            <Input id="new_password" type="password" {...register("new_password")} />
            {errors.new_password && (
              <p className="text-sm text-destructive">{errors.new_password.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Reset password"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function BidderRow({ bidder, clients }: { bidder: BidderUser; clients: ClientUser[] }) {
  const queryClient = useQueryClient();
  const [resetOpen, setResetOpen] = useState(false);
  const clientName = clients.find((c) => c.id === bidder.client_id)?.name ?? bidder.client_id;

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "bidders"] });

  const toggleActive = useMutation({
    mutationFn: () =>
      bidder.is_active ? adminApi.deactivateBidder(bidder.id) : adminApi.reactivateBidder(bidder.id),
    onSuccess: async () => {
      toast.success(bidder.is_active ? "Bidder deactivated" : "Bidder reactivated");
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Action failed")),
  });

  return (
    <TableRow>
      <TableCell className="font-medium">{bidder.name}</TableCell>
      <TableCell>{bidder.username}</TableCell>
      <TableCell>{clientName}</TableCell>
      <TableCell>{bidder.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Inactive</Badge>}</TableCell>
      <TableCell className="space-x-2 text-right">
        <Button
          variant="outline"
          size="sm"
          disabled={toggleActive.isPending}
          onClick={() => toggleActive.mutate()}
        >
          {bidder.is_active ? "Deactivate" : "Reactivate"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => setResetOpen(true)}>
          Reset password
        </Button>
      </TableCell>
      <ResetPasswordDialog bidder={bidder} open={resetOpen} onOpenChange={setResetOpen} />
    </TableRow>
  );
}

export default function AdminBiddersPage() {
  const { data: clients } = useClientOptions();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "bidders"],
    queryFn: () => adminApi.listBidders(),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bidders</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create bidders under a client and assign one of that client&apos;s profiles.
          </p>
        </div>
        <CreateBidderDialog />
      </div>

      <div className="mt-6 rounded-lg border">
        {isLoading && <Skeleton className="m-4 h-32" />}
        {isError && <p className="p-4 text-sm text-destructive">Couldn&apos;t load bidders.</p>}
        {data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No bidders yet.
                  </TableCell>
                </TableRow>
              )}
              {data.map((b) => (
                <BidderRow key={b.id} bidder={b} clients={clients ?? []} />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
