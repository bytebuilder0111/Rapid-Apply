"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
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
import { adminApi } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import type { ClientUser } from "@/lib/types";

const createSchema = z.object({
  name: z.string().min(1, "Name is required."),
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(8, "At least 8 characters."),
});
type CreateValues = z.infer<typeof createSchema>;

const passwordSchema = z.object({ new_password: z.string().min(8, "At least 8 characters.") });
type PasswordValues = z.infer<typeof passwordSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function CreateClientDialog() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({ resolver: zodResolver(createSchema) });

  const onSubmit = async (values: CreateValues) => {
    try {
      await adminApi.createClient(values);
      toast.success("Client created");
      await queryClient.invalidateQueries({ queryKey: ["admin", "clients"] });
      reset();
      setOpen(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't create client"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>New client</Button>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>New client</DialogTitle>
            <DialogDescription>Creates a CLIENT account with the given password.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...register("email")} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" {...register("password")} />
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
  client,
  open,
  onOpenChange,
}: {
  client: ClientUser;
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
      await adminApi.resetClientPassword(client.id, values.new_password);
      toast.success(`Password reset for ${client.email}`);
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
            <DialogDescription>Sets a new password for {client.email}.</DialogDescription>
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

function ClientRow({ client }: { client: ClientUser }) {
  const queryClient = useQueryClient();
  const [resetOpen, setResetOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "clients"] });

  const toggleActive = useMutation({
    mutationFn: () =>
      client.is_active ? adminApi.deactivateClient(client.id) : adminApi.reactivateClient(client.id),
    onSuccess: async () => {
      toast.success(client.is_active ? "Client deactivated" : "Client reactivated");
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Action failed")),
  });

  const deleteClient = useMutation({
    mutationFn: () => adminApi.deleteClient(client.id),
    onSuccess: async () => {
      toast.success("Client deleted");
      setDeleteOpen(false);
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete client")),
  });

  const isDeleted = client.deleted_at !== null;

  return (
    <TableRow>
      <TableCell className="font-medium">{client.name}</TableCell>
      <TableCell>{client.email}</TableCell>
      <TableCell>
        {isDeleted ? (
          <Badge variant="destructive">Deleted</Badge>
        ) : client.is_active ? (
          <Badge>Active</Badge>
        ) : (
          <Badge variant="secondary">Inactive</Badge>
        )}
      </TableCell>
      <TableCell>{new Date(client.created_at).toLocaleDateString()}</TableCell>
      <TableCell className="space-x-2 text-right">
        {!isDeleted && (
          <>
            <Button
              variant="outline"
              size="sm"
              disabled={toggleActive.isPending}
              onClick={() => toggleActive.mutate()}
            >
              {client.is_active ? "Deactivate" : "Reactivate"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setResetOpen(true)}>
              Reset password
            </Button>
            <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </>
        )}
      </TableCell>

      <ResetPasswordDialog client={client} open={resetOpen} onOpenChange={setResetOpen} />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {client.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This soft-deletes the client and deactivates all of their bidders. This can&apos;t be
              undone from the UI.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteClient.isPending}
              onClick={() => deleteClient.mutate()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TableRow>
  );
}

export default function AdminClientsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "clients"],
    queryFn: () => adminApi.listClients(),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Clients</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create and manage client accounts.
          </p>
        </div>
        <CreateClientDialog />
      </div>

      <div className="mt-6 rounded-lg border">
        {isLoading && <Skeleton className="m-4 h-32" />}
        {isError && (
          <p className="p-4 text-sm text-destructive">Couldn&apos;t load clients.</p>
        )}
        {data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No clients yet.
                  </TableCell>
                </TableRow>
              )}
              {data.map((c) => (
                <ClientRow key={c.id} client={c} />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
