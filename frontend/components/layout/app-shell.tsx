"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import { LogOut, Moon, Sun, TriangleAlert } from "lucide-react";
import { useTheme } from "next-themes";

import { useAuth } from "@/components/layout/auth-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { integrationsApi } from "@/lib/integrations-api";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

function initials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "?"
  );
}

export function AppShell({
  navItems,
  roleLabel,
  children,
}: {
  navItems: NavItem[];
  roleLabel: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  const isClientOrBidder = user?.role === "CLIENT" || user?.role === "BIDDER";
  const { data: googleConnection } = useQuery({
    queryKey: ["integrations", "google"],
    queryFn: integrationsApi.getGoogle,
    enabled: isClientOrBidder,
  });
  const needsReconnect = googleConnection?.status === "NEEDS_RECONNECT";

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r bg-muted/30 p-4">
        <div className="mb-6 px-2">
          <p className="text-lg font-semibold">JD Analyzer</p>
          <p className="text-xs text-muted-foreground">{roleLabel}</p>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-2 border-b px-6">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle theme"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            <Sun className="size-4 dark:hidden" />
            <Moon className="hidden size-4 dark:block" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" className="gap-2 px-2">
                  <Avatar className="size-7">
                    <AvatarFallback>{user ? initials(user.name) : "?"}</AvatarFallback>
                  </Avatar>
                  <span className="text-sm">{user?.name}</span>
                </Button>
              }
            />
            <DropdownMenuContent align="end">
              <div className="px-1.5 py-1">
                <p className="text-sm font-medium">{user?.name}</p>
                <p className="text-xs font-normal text-muted-foreground">{user?.username}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="size-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        {needsReconnect && (
          <div className="flex items-center gap-2 border-b bg-destructive/10 px-6 py-2 text-sm text-destructive">
            <TriangleAlert className="size-4 shrink-0" />
            <span>
              The Google connection needs to be reconnected before Sheet recording will work
              again.
            </span>
            {user?.role === "CLIENT" && (
              <Link href="/client/integrations" className="ml-auto underline">
                Reconnect
              </Link>
            )}
          </div>
        )}
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
