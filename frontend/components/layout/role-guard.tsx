"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/layout/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { roleHomePath, type Role } from "@/lib/auth";

export function RoleGuard({ role, children }: { role: Role; children: React.ReactNode }) {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    } else if (status === "authenticated" && user && user.role !== role) {
      router.replace(roleHomePath(user.role));
    }
  }, [status, user, role, router]);

  if (status === "loading" || !user || user.role !== role) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <div className="w-full max-w-sm space-y-3">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
