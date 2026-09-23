"use client";

import { FileText, Plug, Settings, Wand2 } from "lucide-react";

import { AppShell, type NavItem } from "@/components/layout/app-shell";
import { RoleGuard } from "@/components/layout/role-guard";

const navItems: NavItem[] = [
  { label: "Resume Selector", href: "/client", icon: Wand2 },
  { label: "Config", href: "/client/config", icon: Settings },
  { label: "Profiles", href: "/client/profiles", icon: FileText },
  { label: "Integrations", href: "/client/integrations", icon: Plug },
];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard role="CLIENT">
      <AppShell navItems={navItems} roleLabel="Client">
        {children}
      </AppShell>
    </RoleGuard>
  );
}
