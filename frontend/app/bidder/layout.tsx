"use client";

import { Settings, Wand2 } from "lucide-react";

import { AppShell, type NavItem } from "@/components/layout/app-shell";
import { RoleGuard } from "@/components/layout/role-guard";

const navItems: NavItem[] = [
  { label: "Resume Selector", href: "/bidder", icon: Wand2 },
  { label: "Config", href: "/bidder/config", icon: Settings },
];

export default function BidderLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard role="BIDDER">
      <AppShell navItems={navItems} roleLabel="Bidder">
        {children}
      </AppShell>
    </RoleGuard>
  );
}
