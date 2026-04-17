"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth.store";

/**
 * Redirects to /cases if the current user lacks the required permission.
 * Call at the top of any page that requires a specific permission.
 *
 * @param module  e.g. "metrics", "audit", "dispositions"
 * @param action  e.g. "read", "manage"
 */
export function usePermissionGuard(module: string, action: string) {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated) return; // layout already handles unauthenticated redirect

    const permissions = user?.permissions;
    // If permissions haven't loaded yet, wait — don't redirect prematurely
    if (!permissions) return;

    const allowed = permissions.some(
      (p) => p.module === module && p.action === action
    );

    if (!allowed) {
      router.replace("/cases");
    }
  }, [isAuthenticated, user, module, action, router]);
}
