"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useState } from "react";

import { useRefreshFromGlobal } from "@/hooks/useSecurityTaxonomies";
import type { SecurityTaxonomy } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TaxonomyDriftWarningProps {
  taxonomy: SecurityTaxonomy;
  /**
   * Pre-computed signal from the parent: true if this taxonomy is outdated
   * relative to its global source. Computation is centralized in the parent
   * (which has the global source loaded) to avoid duplicate fetches.
   */
  isOutdated: boolean;
  globalUpdatedAt?: string | null;
  onRefreshed?: () => void;
  className?: string;
}

export function TaxonomyDriftWarning({
  taxonomy,
  isOutdated,
  globalUpdatedAt,
  onRefreshed,
  className,
}: TaxonomyDriftWarningProps) {
  const refreshMutation = useRefreshFromGlobal();
  const [error, setError] = useState<string | null>(null);

  // Hide warning if this isn't a fork or it isn't outdated
  if (!taxonomy.forked_from_global_id || !isOutdated) {
    return null;
  }

  async function handleRefresh() {
    setError(null);
    try {
      await refreshMutation.mutateAsync(taxonomy.id);
      onRefreshed?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Refresh failed";
      setError(msg);
    }
  }

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded border border-yellow-400 bg-yellow-50 p-3",
        "dark:border-yellow-700 dark:bg-yellow-950/40",
        className,
      )}
      role="alert"
    >
      <AlertTriangle
        className="h-5 w-5 shrink-0 text-yellow-700 dark:text-yellow-400"
        aria-hidden="true"
      />
      <div className="flex-1 space-y-1">
        <p className="text-sm font-medium text-yellow-900 dark:text-yellow-200">
          Esta taxonomía está desincronizada de la versión global.
        </p>
        {globalUpdatedAt ? (
          <p className="text-xs text-yellow-800 dark:text-yellow-300/80">
            La versión global fue actualizada el{" "}
            {new Date(globalUpdatedAt).toLocaleString()}.
          </p>
        ) : null}
        {error ? (
          <p className="text-xs text-red-700 dark:text-red-400" role="alert">
            {error}
          </p>
        ) : null}
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshMutation.isPending}
          className={cn(
            "mt-1 inline-flex items-center gap-1 rounded border border-yellow-500 bg-yellow-100 px-2.5 py-1 text-xs font-medium text-yellow-900",
            "hover:bg-yellow-200 disabled:cursor-not-allowed disabled:opacity-50",
            "dark:border-yellow-600 dark:bg-yellow-900/40 dark:text-yellow-100 dark:hover:bg-yellow-900/60",
          )}
        >
          <RefreshCw
            className={cn(
              "h-3.5 w-3.5",
              refreshMutation.isPending && "animate-spin",
            )}
          />
          {refreshMutation.isPending ? "Re-syncing..." : "Re-sync desde global"}
        </button>
      </div>
    </div>
  );
}
