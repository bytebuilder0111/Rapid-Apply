"use client";

import { useEffect, useState } from "react";
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { integrationsApi } from "@/lib/integrations-api";

function GoogleIntegrationCard() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["integrations", "google"],
    queryFn: integrationsApi.getGoogle,
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("google");
    if (!result) return;
    if (result === "connected") toast.success("Google account connected");
    if (result === "error") toast.error("Couldn't connect Google account");
    window.history.replaceState(null, "", window.location.pathname);
    queryClient.invalidateQueries({ queryKey: ["integrations", "google"] });
    // Runs once on mount to consume the OAuth redirect's query params.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = useMutation({
    mutationFn: integrationsApi.getGoogleAuthorizeUrl,
    onSuccess: (data) => {
      window.location.href = data.authorize_url;
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Couldn't start Google sign-in"),
  });

  const disconnect = useMutation({
    mutationFn: integrationsApi.disconnectGoogle,
    onSuccess: async () => {
      toast.success("Google account disconnected");
      await queryClient.invalidateQueries({ queryKey: ["integrations", "google"] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Couldn't disconnect"),
  });

  return (
    <Card className="mt-6 max-w-lg">
      <CardHeader>
        <CardTitle>Google</CardTitle>
        <CardDescription>
          Used to record saved analyses into a spreadsheet — see Config.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-16" />}
        {isError && <p className="text-sm text-destructive">Couldn&apos;t load Google status.</p>}
        {data && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Status:</span>
              {data.connected ? (
                <Badge variant={data.status === "NEEDS_RECONNECT" ? "destructive" : "default"}>
                  {data.status === "NEEDS_RECONNECT" ? "Needs reconnect" : data.email}
                </Badge>
              ) : (
                <Badge variant="secondary">Not connected</Badge>
              )}
            </div>
            <div className="flex gap-2">
              <Button disabled={connect.isPending} onClick={() => connect.mutate()}>
                {data.connected ? "Reconnect Google" : "Connect Google"}
              </Button>
              {data.connected && (
                <Button
                  type="button"
                  variant="destructive"
                  disabled={disconnect.isPending}
                  onClick={() => disconnect.mutate()}
                >
                  Disconnect
                </Button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const formSchema = z.object({
  api_key: z.string().min(1, "API key is required."),
  model: z.string().min(1, "Model is required."),
});
type FormValues = z.infer<typeof formSchema>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export default function ClientIntegrationsPage() {
  const queryClient = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["integrations", "openai"],
    queryFn: integrationsApi.getOpenAi,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { api_key: "", model: "" },
  });

  useEffect(() => {
    if (data) reset({ api_key: "", model: data.model });
  }, [data, reset]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["integrations", "openai"] });

  const save = async (values: FormValues) => {
    try {
      await integrationsApi.saveOpenAi(values);
      toast.success("OpenAI key saved");
      await invalidate();
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't save key"));
    }
  };

  const testKey = useMutation({
    mutationFn: integrationsApi.testOpenAi,
    onSuccess: () => toast.success("Key works"),
    onError: (error) => toast.error(errorMessage(error, "Key test failed")),
  });

  const deleteKey = useMutation({
    mutationFn: integrationsApi.deleteOpenAi,
    onSuccess: async () => {
      toast.success("Key deleted");
      setDeleteOpen(false);
      await invalidate();
    },
    onError: (error) => toast.error(errorMessage(error, "Couldn't delete key")),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Connect the OpenAI key used for JD analysis and the Google account used to record
        analyses.
      </p>

      <Card className="mt-6 max-w-lg">
        <CardHeader>
          <CardTitle>OpenAI</CardTitle>
          <CardDescription>Stored encrypted. Never sent back to the browser in full.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-32" />}
          {isError && <p className="text-sm text-destructive">Couldn&apos;t load settings.</p>}
          {data && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Status:</span>
                {data.has_key ? (
                  <Badge>Connected · {data.masked_key}</Badge>
                ) : (
                  <Badge variant="secondary">Not connected</Badge>
                )}
              </div>

              <form className="flex flex-col gap-4" onSubmit={handleSubmit(save)}>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="api_key">
                    {data.has_key ? "Replace API key" : "API key"}
                  </Label>
                  <Input
                    id="api_key"
                    type="password"
                    placeholder="sk-..."
                    {...register("api_key")}
                  />
                  {errors.api_key && (
                    <p className="text-sm text-destructive">{errors.api_key.message}</p>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="model">Model</Label>
                  <Input id="model" {...register("model")} />
                  {errors.model && (
                    <p className="text-sm text-destructive">{errors.model.message}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!data.has_key || testKey.isPending}
                    onClick={() => testKey.mutate()}
                  >
                    {testKey.isPending ? "Testing..." : "Test key"}
                  </Button>
                  {data.has_key && (
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={() => setDeleteOpen(true)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </form>
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete OpenAI key?</AlertDialogTitle>
            <AlertDialogDescription>
              Analyze will stop working for this client and its bidders until a new key is added.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={deleteKey.isPending} onClick={() => deleteKey.mutate()}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <GoogleIntegrationCard />
    </div>
  );
}
