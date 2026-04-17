"use client";

import { useAuthStore } from "@/store/auth.store";

const EMPTY_PERMISSIONS: never[] = [];

/**
 * Returns true if the current user has the given permission.
 * Optionally filters by scope (e.g. "all", "own").
 *
 * Usage:
 *   const canAssign  = useHasPermission("cases", "assign");
 *   const canArchive = useHasPermission("cases", "archive");
 *   const adminAssign = useHasPermission("cases", "assign", "all");
 */
export function useHasPermission(module: string, action: string, scope?: string): boolean {
  const permissions = useAuthStore((s) => s.user?.permissions ?? EMPTY_PERMISSIONS);
  return permissions.some(
    (p) =>
      p.module === module &&
      p.action === action &&
      (scope === undefined || p.scope === scope)
  );
}
