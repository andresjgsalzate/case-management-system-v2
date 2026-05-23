"use client";

import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Database,
  ExternalLink,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { useHasPermission } from "@/hooks/useHasPermission";
import { useMitreRefresh } from "@/hooks/useMitreRefresh";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";

/**
 * Operator surface for the MITRE catalog cache. Read-only by default;
 * users with `security_taxonomies:manage_global` get the "Actualizar
 * ahora" button that POSTs /api/v1/mitre/refresh, busts the 24 h
 * Redis cache, and forces a live fetch from MITRE's CTI mirror.
 */
export default function MitreCatalogPage() {
  usePermissionGuard("security_taxonomies", "read");
  const canRefresh = useHasPermission("security_taxonomies", "manage_global");
  const refresh = useMitreRefresh();

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <div>
        <Link
          href="/settings"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Configuración
        </Link>
        <h1 className="text-xl font-semibold text-foreground">
          Catálogo MITRE ATT&amp;CK
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Origen: MITRE Enterprise (mirror de GitHub). El catálogo
          alimenta el picker de técnicas en el editor de taxonomías.
        </p>
      </div>

      {/* Source chain card */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-start gap-3">
          <Database className="h-5 w-5 mt-0.5 text-purple-500 shrink-0" />
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-foreground">
              Cómo se resuelve una búsqueda
            </h2>
            <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs text-muted-foreground">
              <li>
                Cache Redis (TTL 24 h) — la mayoría de búsquedas salen de
                aquí, instantáneas.
              </li>
              <li>
                Fetch live al{" "}
                <a
                  href="https://github.com/mitre/cti"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-0.5 text-primary hover:underline"
                >
                  STIX bundle de MITRE
                  <ExternalLink className="h-3 w-3" />
                </a>{" "}
                (≈45 MB) cuando el cache caduca.
              </li>
              <li>
                Snapshot bundleado en{" "}
                <code className="text-[11px]">data/mitre/techniques.json</code>{" "}
                si MITRE no responde — red de seguridad.
              </li>
            </ol>
          </div>
        </div>
      </div>

      {/* Manual refresh card */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              Forzar actualización
            </h2>
            <p className="mt-1 text-xs text-muted-foreground max-w-md">
              Invalida el cache Redis y descarga la versión más reciente.
              Útil cuando MITRE publica una release nueva y no querés
              esperar al ciclo natural de 24 h.
            </p>
          </div>
          {canRefresh ? (
            <Button
              onClick={() => refresh.mutate()}
              loading={refresh.isPending}
              disabled={refresh.isPending}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Actualizar ahora
            </Button>
          ) : (
            <span className="text-xs text-muted-foreground self-center">
              Requiere permiso{" "}
              <code className="text-[11px]">
                security_taxonomies:manage_global
              </code>
            </span>
          )}
        </div>

        {refresh.isSuccess && refresh.data && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-emerald-50 p-2 text-xs text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
            <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium">
                Catálogo actualizado: {refresh.data.count} técnicas.
              </p>
              <p className="text-emerald-700 dark:text-emerald-300">
                Próximo refresh automático en {Math.round(refresh.data.ttl_seconds / 3600)}{" "}
                horas.
              </p>
            </div>
          </div>
        )}

        {refresh.isError && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-rose-50 p-2 text-xs text-rose-900 dark:bg-rose-950/30 dark:text-rose-200">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium">No se pudo actualizar.</p>
              <p className="text-rose-700 dark:text-rose-300">
                {refresh.error?.message ??
                  "Reintenta en unos minutos o revisa los logs del backend."}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
