"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { LogOut, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar } from "@/components/atoms/Avatar";
import { NotificationBell } from "@/components/molecules/NotificationBell";
import { ThemeToggle } from "@/components/molecules/ThemeToggle";
import { useAuthStore } from "@/store/auth.store";

export function Header() {
  const { user, logout } = useAuthStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <header className="h-14 border-b border-border bg-card flex items-center px-4 gap-4 shrink-0">
      {/* Spacer */}
      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-1">
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
