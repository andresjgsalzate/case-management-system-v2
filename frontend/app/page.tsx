"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth.store";

/**
 * Root redirect. Sends users to their "home" based on permissions:
 * - metrics/read  → /metrics  (resolvers, admins)
 * - otherwise     → /cases    (reporters, limited roles)
 */
export default function HomePage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }

    const permissions = user?.permissions ?? [];
    const hasMetrics = permissions.some(
      (p) => p.module === "metrics" && p.action === "read"
    );

    router.replace(hasMetrics ? "/metrics" : "/cases");
  }, [isAuthenticated, user, router]);

  return null;
}
