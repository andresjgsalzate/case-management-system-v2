import type { UserPermission } from "@/lib/types";

/**
 * Check if a list of UserPermissions includes the (module, action) pair.
 *
 * Graceful degradation: if `permissions` is undefined (user still loading),
 * returns `true` to avoid flicker — UI shows the action; backend will still
 * enforce permission via PermissionChecker.
 */
export function hasPermission(
  permissions: UserPermission[] | undefined,
  module: string,
  action: string,
): boolean {
  if (!permissions) return true;
  return permissions.some((p) => p.module === module && p.action === action);
}
