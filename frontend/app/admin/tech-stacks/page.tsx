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
import { ApiError } from "@/lib/api";
import { adminTechStacksApi } from "@/lib/tech-stacks-api";
import type { TechStack } from "@/lib/types";

const createSchema = z.object({ name: z.string().min(1, "Name is required.") });
type CreateValues = z.infer<typeof createSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function CreateTechStackDialog() {
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
      await adminTechStacksApi.create(values.name);
      toast.success("Tech stack created");
      await queryClient.invalidateQueries({ queryKey: ["admin", "tech-stacks"] });
      reset();
      setOpen(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't create tech stack"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button onClick={() => setOpen(true)}>New tech stack</Button>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>New tech stack</DialogTitle>
            <DialogDescription>
              Immediately available to clients as a Primary Tech Stack option.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-4">
            <Label htmlFor="name">Name</Label>
            <Input id="name" placeholder="Rust/Actix" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
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

function RenameTechStackDialog({
  stack,
  open,
  onOpenChange,
}: {
  stack: TechStack;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    values: { name: stack.name },
  });

  const onSubmit = async (values: CreateValues) => {
    try {
      await adminTechStacksApi.update(stack.id, { name: values.name });
      toast.success("Tech stack renamed");
      await queryClient.invalidateQueries({ queryKey: ["admin", "tech-stacks"] });
      onOpenChange(false);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't rename tech stack"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Rename tech stack</DialogTitle>
            <DialogDescription>
              Existing profiles keep their current value; only new/edited profiles see the new
              name.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-4">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TechStackRow({ stack }: { stack: TechStack }) {
  const queryClient = useQueryClient();
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "tech-stacks"] });

  const toggleActive = useMutation({
    mutationFn: () => adminTechStacksApi.update(stack.id, { is_active: !stack.is_active }),
    onSuccess: async () => {
      toast.success(stack.is_active ? "Deactivated" : "Activated");
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Action failed")),
  });

  const remove = useMutation({
    mutationFn: () => adminTechStacksApi.remove(stack.id),
    onSuccess: async () => {
      toast.success("Tech stack deleted");
      setDeleteOpen(false);
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete tech stack")),
  });

  return (
    <TableRow>
      <TableCell className="font-medium">{stack.name}</TableCell>
      <TableCell>
        {stack.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Inactive</Badge>}
      </TableCell>
      <TableCell className="space-x-2 text-right">
        <Button
          variant="outline"
          size="sm"
          disabled={toggleActive.isPending}
          onClick={() => toggleActive.mutate()}
        >
          {stack.is_active ? "Deactivate" : "Activate"}
        </Button>
        <Button variant="outline" size="sm" onClick={() => setRenameOpen(true)}>
          Rename
        </Button>
        <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
          Delete
        </Button>
      </TableCell>

      <RenameTechStackDialog stack={stack} open={renameOpen} onOpenChange={setRenameOpen} />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {stack.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Profiles already using this stack keep their value, but it won&apos;t be selectable
              anymore.
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

export default function AdminTechStacksPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "tech-stacks"],
    queryFn: () => adminTechStacksApi.listAll(),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tech Stacks</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            The list clients pick from as a profile&apos;s Primary Tech Stack.
          </p>
        </div>
        <CreateTechStackDialog />
      </div>

      <div className="mt-6 rounded-lg border">
        {isLoading && <Skeleton className="m-4 h-32" />}
        {isError && <p className="p-4 text-sm text-destructive">Couldn&apos;t load tech stacks.</p>}
        {data && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-muted-foreground">
                    No tech stacks yet.
                  </TableCell>
                </TableRow>
              )}
              {data.map((s) => (
                <TechStackRow key={s.id} stack={s} />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
