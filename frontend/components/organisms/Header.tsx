"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  LogOut,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar } from "@/components/atoms/Avatar";
import { NotificationBell } from "@/components/molecules/NotificationBell";
import { ThemeToggle } from "@/components/molecules/ThemeToggle";
import { Breadcrumb } from "@/components/molecules/Breadcrumb";
import { GlobalCaseSearch } from "@/components/molecules/GlobalCaseSearch";
import { useAuthStore } from "@/store/auth.store";
import { getUserManager } from "@/lib/keycloak";

export function Header() {
  const { user, logout, setUser } = useAuthStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  const isN8nPage = pathname === "/n8n";

  function handleN8nBack() {
    // Prefer the user's previous in-CMS location; fall back to /metrics
    // when no usable history (bookmark / direct URL).
    if (
      typeof window !== "undefined" &&
      document.referrer &&
      document.referrer.startsWith(window.location.origin) &&
      window.history.length > 1
    ) {
      router.back();
    } else {
      router.push("/metrics");
    }
  }

  // Fetch profile if user object is missing (e.g. session restored from token only)
  useEffect(() => {
    if (!user) {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      if (token) {
        import("@/lib/apiClient").then(({ apiClient }) => {
          apiClient.get("/auth/me").then(({ data }) => {
            if (data?.data) setUser(data.data);
          }).catch(() => {});
        });
      }
    }
  }, [user, setUser]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function handleLogout() {
    // Clear local state first so the user is logged out even if the
    // Keycloak round-trip fails (network blip, IdP down).
    logout();
    try {
      // Terminates the Keycloak SSO session and redirects to the
      // `post_logout_redirect_uri` configured on the UserManager
      // (/login). Without this step the user lands on /login but
      // Keycloak still has a session, so auto-redirect silently
      // logs them right back in.
      await getUserManager().signoutRedirect();
    } catch {
      // Fallback: stay local. Auto-redirect on /login will hit
      // Keycloak which may or may not have a session; the user can
      // explicitly use ?prompt=login.
      router.push("/login");
    }
  }

  return (
    <header className="h-14 border-b border-border bg-card flex items-center px-4 gap-4 shrink-0">
      {/* Breadcrumb — izquierda, crece para empujar las acciones a la derecha */}
      <div className="flex-1 min-w-0">
        <Breadcrumb />
      </div>

      {/* Page-specific actions (currently only /n8n needs them) — sit
          between the breadcrumb and the global utilities so they're
          contextually grouped with the route, not the user identity. */}
      {isN8nPage && (
        <div className="flex items-center gap-1 border-r border-border pr-2 mr-1">
          <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Workflow className="h-3.5 w-3.5 text-purple-500" />
            <span className="font-medium text-foreground">Editor n8n</span>
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              Single-admin
            </span>
          </span>
          <button
            type="button"
            onClick={handleN8nBack}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Salir del editor n8n"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Volver
          </button>
          <Link
            href="/n8n/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Abrir n8n en una pestaña nueva sin chrome del CMS"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Pantalla completa
          </Link>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1">
        <GlobalCaseSearch />
        <ThemeToggle />
        <NotificationBell />

        {/* User menu */}
        <div className="relative ml-1" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            className={cn(
              "flex items-center gap-2 px-2 py-1.5 rounded-md",
              "hover:bg-muted transition-colors duration-150"
            )}
          >
            <Avatar name={user?.full_name ?? "Usuario"} src={user?.avatar_url} size="sm" />
            <span className="hidden sm:block text-sm font-medium text-foreground truncate max-w-32">
              {user?.full_name ?? "Usuario"}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-10 z-50 w-48 rounded-lg border border-border bg-card shadow-lg overflow-hidden">
              <div className="px-3 py-2 border-b border-border">
                <p className="text-xs font-medium text-foreground truncate">{user?.full_name}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-muted transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                  Cerrar sesión
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
