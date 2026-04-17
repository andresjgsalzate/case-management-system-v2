"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

// ── Etiquetas por segmento de ruta ────────────────────────────────────────────
const SEGMENT_LABELS: Record<string, string> = {
  cases:          "Casos",
  archive:        "Archivo",
  metrics:        "Métricas",
  audit:          "Auditoría",
  dispositions:   "Disposiciones",
  kb:             "Base de Conocimiento",
  teams:          "Equipos",
  settings:       "Configuración",
  new:            "Nuevo",
  // settings sub-pages
  users:          "Usuarios",
  roles:          "Roles",
  statuses:       "Estados",
  priorities:     "Prioridades",
  classification: "Clasificación",
  applications:   "Aplicaciones",
  origins:        "Orígenes",
  sla:            "SLA",
  "case-numbers": "Numeración de casos",
  automation:     "Automatización",
  notifications:  "Notificaciones",
  email:          "Correo",
  tenants:        "Tenants",
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function labelFor(segment: string): string {
  if (UUID_RE.test(segment)) return "Detalle";
  return SEGMENT_LABELS[segment] ?? segment;
}

export function Breadcrumb() {
  const pathname = usePathname();

  // Split into non-empty segments, ignore the leading ""
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  // Build cumulative href for each crumb
  const crumbs = segments.map((seg, i) => ({
    label: labelFor(seg),
    href: "/" + segments.slice(0, i + 1).join("/"),
    isLast: i === segments.length - 1,
  }));

  return (
    <nav aria-label="Miga de pan" className="flex items-center gap-1 text-sm min-w-0">
      {crumbs.map((crumb, i) => (
        <span key={crumb.href} className="flex items-center gap-1 min-w-0">
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />}
          {crumb.isLast ? (
            <span className="font-medium text-foreground truncate max-w-48">
              {crumb.label}
            </span>
          ) : (
            <Link
              href={crumb.href}
              className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-40"
            >
              {crumb.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
