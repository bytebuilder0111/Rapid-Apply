"use client";

import { FileText, LayoutDashboard, UserPlus, Users } from "lucide-react";

import { AppShell, type NavItem } from "@/components/layout/app-shell";
import { RoleGuard } from "@/components/layout/role-guard";

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/admin", icon: LayoutDashboard },
  { label: "Clients", href: "/admin/clients", icon: Users },
  { label: "Bidders", href: "/admin/bidders", icon: UserPlus },
  { label: "Resume Types", href: "/admin/profiles", icon: FileText },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard role="ADMIN">
      <AppShell navItems={navItems} roleLabel="Admin">
        {children}
      </AppShell>
    </RoleGuard>
  );
}
