"use client";

import { usePermissionGuard } from "@/hooks/usePermissionGuard";

/**
 * Guard all /settings/* routes — only users with roles/manage can access them.
 */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  usePermissionGuard("roles", "manage");
  return <>{children}</>;
}
