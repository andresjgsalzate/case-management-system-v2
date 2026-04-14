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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/store/ui.store";

const NAV_ITEMS = [
  { href: "/metrics",      label: "Dashboard",            icon: LayoutDashboard, color: "text-blue-500" },
  { href: "/cases",        label: "Casos",                icon: FolderOpen,      color: "text-amber-500" },
  { href: "/kb",           label: "Base de conocimiento", icon: BookOpen,        color: "text-emerald-500" },
  { href: "/audit",        label: "Auditoría",            icon: Shield,          color: "text-violet-500" },
  { href: "/dispositions", label: "Disposiciones",        icon: Tag,             color: "text-cyan-500" },
];

const BOTTOM_ITEMS = [
  { href: "/settings", label: "Configuración", icon: Settings, color: "text-orange-500" },
];

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
        {NAV_ITEMS.map((item) => (
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
        {BOTTOM_ITEMS.map((item) => (
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
