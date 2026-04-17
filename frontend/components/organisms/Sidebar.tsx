"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  BookOpen,
  Shield,
  Tag,
  Settings,
  ChevronLeft,
  ChevronRight,
  Briefcase,
  Archive,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/store/ui.store";
import { useAuthStore } from "@/store/auth.store";
import type { UserPermission } from "@/lib/types";

interface NavItemDef {
  href: string;
  label: string;
  icon: React.ElementType;
  color: string;
  /** If set, only shown when the user has this permission */
  permission?: { module: string; action: string };
}

const NAV_ITEMS: NavItemDef[] = [
  { href: "/metrics",      label: "Dashboard",            icon: LayoutDashboard, color: "text-blue-500",    permission: { module: "metrics",        action: "read" } },
  { href: "/cases",        label: "Casos",                icon: FolderOpen,      color: "text-amber-500",   permission: { module: "cases",          action: "read" } },
  { href: "/dispositions", label: "Disposiciones",        icon: Tag,             color: "text-cyan-500",    permission: { module: "dispositions",    action: "read" } },
  { href: "/kb",           label: "Base de conocimiento", icon: BookOpen,        color: "text-emerald-500", permission: { module: "knowledge_base",  action: "read" } },
  { href: "/archive",      label: "Archivo",              icon: Archive,         color: "text-slate-500",   permission: { module: "cases",           action: "read" } },
  { href: "/audit",        label: "Auditoría",            icon: Shield,          color: "text-violet-500",  permission: { module: "audit",           action: "read" } },
];

const BOTTOM_ITEMS: NavItemDef[] = [
  { href: "/settings", label: "Configuración", icon: Settings, color: "text-orange-500", permission: { module: "roles", action: "manage" } },
];

function hasPermission(permissions: UserPermission[] | undefined, module: string, action: string): boolean {
  if (!permissions) return true; // no permissions loaded yet → show all (graceful degradation)
  return permissions.some((p) => p.module === module && p.action === action);
}

interface NavItemProps {
  href: string;
  label: string;
  icon: React.ElementType;
  color: string;
  collapsed: boolean;
}

function NavItem({ href, label, icon: Icon, color, collapsed }: NavItemProps) {
  const pathname = usePathname();
  const isActive = pathname.startsWith(href);

  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150",
        isActive
          ? "bg-[hsl(var(--sidebar-item-active-bg))] text-[hsl(var(--sidebar-item-active-text))]"
          : "text-muted-foreground hover:text-foreground hover:bg-[hsl(var(--sidebar-item-hover))]",
        collapsed && "justify-center px-2"
      )}
    >
      <Icon
        className={cn(
          "shrink-0",
          collapsed ? "h-5 w-5" : "h-4 w-4",
          isActive ? "text-[hsl(var(--sidebar-item-active-text))]" : color
        )}
      />
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
}

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { user } = useAuthStore();
  const permissions = user?.permissions;

  const visibleNavItems = NAV_ITEMS.filter((item) =>
    !item.permission || hasPermission(permissions, item.permission.module, item.permission.action)
  );
  const visibleBottomItems = BOTTOM_ITEMS.filter((item) =>
    !item.permission || hasPermission(permissions, item.permission.module, item.permission.action)
  );

  return (
    <aside
      className={cn(
        "flex flex-col h-full shrink-0",
        "border-r border-[hsl(var(--sidebar-border))]",
        "bg-[hsl(var(--sidebar-bg))]",
        "shadow-[1px_0_8px_0_rgba(0,0,0,0.06)]",
        "transition-[width] duration-200 ease-in-out",
        sidebarCollapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex items-center h-14 px-4 shrink-0",
          "border-b border-[hsl(var(--sidebar-border))]",
          sidebarCollapsed ? "justify-center" : "gap-2.5"
        )}
      >
        <div className="h-7 w-7 rounded-md bg-primary flex items-center justify-center shrink-0 shadow-sm">
          <Briefcase className="h-4 w-4 text-primary-foreground" />
        </div>
        {!sidebarCollapsed && (
          <span className="font-semibold text-sm text-foreground tracking-tight truncate">
            CaseManager
          </span>
        )}
      </div>

      {/* Nav principal */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 flex flex-col gap-0.5">
        {visibleNavItems.map((item) => (
          <NavItem key={item.href} {...item} collapsed={sidebarCollapsed} />
        ))}
      </nav>

      {/* Sección inferior */}
      <div
        className={cn(
          "py-3 px-2 flex flex-col gap-0.5",
          "border-t border-[hsl(var(--sidebar-border))]"
        )}
      >
        {visibleBottomItems.map((item) => (
          <NavItem key={item.href} {...item} collapsed={sidebarCollapsed} />
        ))}

        <button
          type="button"
          onClick={toggleSidebar}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium",
            "text-muted-foreground hover:text-foreground",
            "hover:bg-[hsl(var(--sidebar-item-hover))] transition-colors",
            sidebarCollapsed && "justify-center px-2"
          )}
          title={sidebarCollapsed ? "Expandir" : "Colapsar"}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4 shrink-0 text-slate-400" />
              <span>Colapsar</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
