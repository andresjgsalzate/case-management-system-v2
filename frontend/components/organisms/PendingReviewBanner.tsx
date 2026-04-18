"use client";

import Link from "next/link";
import { ClipboardCheck, ChevronRight } from "lucide-react";
import { usePendingReview } from "@/hooks/useKB";
import { useAuthStore } from "@/store/auth.store";
import type { UserPermission } from "@/lib/types";

function hasManageKB(perms: UserPermission[] | undefined): boolean {
  if (!perms) return false;
  return perms.some(
    (p) => p.module === "knowledge_base" && p.action === "manage"
  );
}

export function PendingReviewBanner() {
  const perms = useAuthStore((s) => s.user?.permissions);
  const canManage = hasManageKB(perms);
  const { data: pending = [], isLoading } = usePendingReview();

  if (!canManage || isLoading || pending.length === 0) return null;

  return (
    <Link
      href="/kb?status=in_review"
      className="flex items-center justify-between gap-3 rounded-lg border border-amber-300/40 bg-amber-50 p-3 hover:bg-amber-100 dark:bg-amber-900/20 dark:border-amber-700/40 dark:hover:bg-amber-900/30 transition-colors"
    >
      <div className="flex items-center gap-2.5">
        <ClipboardCheck className="h-4 w-4 text-amber-700 dark:text-amber-300" />
        <div>
          <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
            {pending.length} artículo{pending.length !== 1 ? "s" : ""} pendiente
            {pending.length !== 1 ? "s" : ""} de revisión
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-300">
            Haz clic para ver el listado completo
          </p>
        </div>
      </div>
      <ChevronRight className="h-4 w-4 text-amber-700 dark:text-amber-300" />
    </Link>
  );
}
