"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  BookOpen,
  Users,
  BarChart2,
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
  { href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/cases", label: "Casos", icon: FolderOpen },
  { href: "/kb", label: "Base de conocimiento", icon: BookOpen },
  { href: "/teams", label: "Equipos", icon: Users },
  { href: "/metrics", label: "Métricas", icon: BarChart2 },
  { href: "/audit", label: "Auditoría", icon: Shield },
  { href: "/dispositions", label: "Disposiciones", icon: Tag },
];

const BOTTOM_ITEMS = [
  { href: "/settings", label: "Configuración", icon: Settings },
];

interface NavItemProps {
  href: string;
  label: string;
  icon: React.ElementType;
  collapsed: boolean;
  exact?: boolean;
}

function NavItem({ href, label, icon: Icon, collapsed, exact }: NavItemProps) {
  const pathname = usePathname();
  const isActive = exact ? pathname === href : pathname.startsWith(href);

  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150",
        "hover:bg-sidebar-item-hover",
        isActive
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:text-foreground"
      )}
    >
      <Icon className={cn("shrink-0", collapsed ? "h-5 w-5" : "h-4 w-4")} />
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
}

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        "flex flex-col h-full border-r border-border bg-card",
        "transition-[width] duration-200 ease-in-out",
        sidebarCollapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className={cn(
        "flex items-center h-14 px-4 border-b border-border shrink-0",
        sidebarCollapsed ? "justify-center" : "gap-2"
      )}>
        <div className="h-7 w-7 rounded-md bg-primary flex items-center justify-center shrink-0">
          <Briefcase className="h-4 w-4 text-primary-foreground" />
        </div>
        {!sidebarCollapsed && (
          <span className="font-semibold text-sm text-foreground truncate">
            CaseManager
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.href} {...item} collapsed={sidebarCollapsed} />
        ))}
      </nav>

      {/* Bottom */}
      <div className="py-3 px-2 border-t border-border flex flex-col gap-0.5">
        {BOTTOM_ITEMS.map((item) => (
          <NavItem key={item.href} {...item} collapsed={sidebarCollapsed} />
        ))}

        {/* Collapse toggle */}
        <button
          type="button"
          onClick={toggleSidebar}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium",
            "text-muted-foreground hover:text-foreground hover:bg-muted transition-colors",
            sidebarCollapsed && "justify-center"
          )}
          title={sidebarCollapsed ? "Expandir sidebar" : "Colapsar sidebar"}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-4 w-4 shrink-0" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4 shrink-0" />
              <span>Colapsar</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
