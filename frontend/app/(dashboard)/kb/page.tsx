"use client";

import { useMemo, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Plus, BookOpen, Eye, ThumbsUp, User, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { KBSearchPanel } from "@/components/organisms/KBSearchPanel";
import { searchArticles, scoreBand, type Filter } from "@/lib/kb-search";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { DocumentTypeBadge } from "@/components/molecules/DocumentTypeBadge";
import { VisibilityBadge } from "@/components/molecules/VisibilityBadge";
import { Spinner } from "@/components/atoms/Spinner";
import { useKBArticles, useKBTags } from "@/hooks/useKB";
import { PendingReviewBanner } from "@/components/organisms/PendingReviewBanner";
// formatDate y truncate ya no se usan — los stats inferiores fueron simplificados
import type { KBStatus } from "@/lib/types";

const PAGE_SIZE = 12;

const STATUS_TABS: { label: string; value: KBStatus | "" }[] = [
  { label: "Todos", value: "" },
  { label: "Publicados", value: "published" },
  { label: "En revisión", value: "in_review" },
  { label: "Borradores", value: "draft" },
  { label: "Rechazados", value: "rejected" },
];

const VALID_STATUSES: KBStatus[] = ["draft", "in_review", "approved", "rejected", "published"];

function parseStatusParam(raw: string | null): KBStatus | "" {
  return raw && (VALID_STATUSES as string[]).includes(raw) ? (raw as KBStatus) : "";
}

export default function KBPage() {
  usePermissionGuard("knowledge_base", "read");
  const searchParams = useSearchParams();
  const initialTagSlug = searchParams.get("tag") ?? "";
  const initialStatus = parseStatusParam(searchParams.get("status"));

  const [filters, setFilters] = useState<Filter[]>([]);
  const [activeStatus, setActiveStatus] = useState<KBStatus | "">(initialStatus);
  const [activeTagSlug, setActiveTagSlug] = useState<string>(initialTagSlug);
  const [currentPage, setCurrentPage] = useState(1);
  const { data: tags = [] } = useKBTags();

  // Sincroniza si los query params cambian — útil cuando el usuario llega vía
  // links externos ("?tag=bug") o desde el banner de pendientes ("?status=in_review")
  // sin desmontar el componente.
  useEffect(() => {
    setActiveTagSlug(searchParams.get("tag") ?? "");
    setActiveStatus(parseStatusParam(searchParams.get("status")));
  }, [searchParams]);

  // Reset to page 1 when filters/status/tag change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters, activeStatus, activeTagSlug]);

  const { data: articles = [], isLoading } = useKBArticles(
    activeStatus || undefined,
    activeTagSlug || undefined,
  );

  const scoredArticles = useMemo(
    () => searchArticles(articles, filters),
    [articles, filters],
  );

  const totalPages = Math.ceil(scoredArticles.length / PAGE_SIZE);
  const pagedArticles = scoredArticles.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  return (
    <div className="flex flex-col gap-5">
      <PendingReviewBanner />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Base de Conocimiento</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${scoredArticles.length} artículo${scoredArticles.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Link href="/kb/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            Nuevo artículo
          </Button>
        </Link>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <KBSearchPanel
          filters={filters}
          onFiltersChange={setFilters}
          className="sm:w-96"
        />
        <div className="flex items-center gap-1 overflow-x-auto">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveStatus(tab.value)}
              className={`px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition-colors ${
                activeStatus === tab.value
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {tags.length > 0 && (
        <div className="flex items-center gap-1 overflow-x-auto">
          <button
            type="button"
            onClick={() => setActiveTagSlug("")}
            className={`px-2.5 py-1 rounded-md text-xs whitespace-nowrap transition-colors ${
              activeTagSlug === ""
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            Todos los tags
          </button>
          {tags.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTagSlug(t.slug)}
              className={`px-2.5 py-1 rounded-md text-xs whitespace-nowrap transition-colors ${
                activeTagSlug === t.slug
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!isLoading && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {pagedArticles.length === 0 && (
              <div className="col-span-full rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
                <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">
                  {filters.length === 0
                    ? "No hay artículos que mostrar"
                    : "0 resultados — refina con menos filtros o desactiva el modo exacto"}
                </p>
              </div>
            )}
            {pagedArticles.map(({ article, score, matched }) => (
              <Link
                key={article.id}
                href={`/kb/${article.id}`}
                className="rounded-lg border border-border bg-card p-3.5 hover:border-primary/30 hover:shadow-sm transition-all duration-150 flex flex-col gap-2"
              >
                {score != null && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span
                      className={cn(
                        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium",
                        scoreBand(score) === "excelente" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
                        scoreBand(score) === "muy-bueno" && "bg-sky-500/10 text-sky-700 dark:text-sky-300",
                        scoreBand(score) === "bueno" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
                        scoreBand(score) === "parcial" && "bg-slate-500/10 text-slate-600 dark:text-slate-400",
                      )}
                    >
                      {Math.round(score)}%
                    </span>
                    {matched.map((m) => (
                      <span
                        key={m}
                        className={cn(
                          "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold",
                          m === "T" && "bg-blue-500/10 text-blue-700 dark:text-blue-300",
                          m === "C" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
                          m === "E" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
                          m === "CA" && "bg-purple-500/10 text-purple-700 dark:text-purple-300",
                        )}
                        title={
                          m === "T" ? "Coincide en Título" :
                          m === "C" ? "Coincide en Contenido" :
                          m === "E" ? "Coincide en Etiquetas" :
                          "Coincide en Casos asociados"
                        }
                      >
                        {m}
                      </span>
                    ))}
                  </div>
                )}
                {/* Status + versión: línea pequeña arriba (info de estado del documento) */}
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusBadge status={article.status} />
                  <span className="text-xs text-muted-foreground">v{article.version}</span>
                </div>

                {/* 1. Título */}
                <h3 className="font-semibold text-foreground hover:text-primary transition-colors line-clamp-2">
                  {article.title}
                </h3>

                {/* 2. Tipo de documento + 3. Visibilidad */}
                <div className="flex items-center gap-2 flex-wrap">
                  <DocumentTypeBadge type={article.document_type} />
                  <VisibilityBadge visibility={article.visibility} />
                </div>

                {/* 4. Tags */}
                {article.tags && article.tags.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {article.tags.map((t) => (
                      <span
                        key={t.id}
                        className="inline-flex items-center rounded-md bg-primary/10 text-primary text-xs px-2 py-0.5"
                      >
                        {t.name}
                      </span>
                    ))}
                  </div>
                )}

                {/* 5. Creador + stats — fila final, empuja al fondo del card */}
                <div className="flex items-center gap-3 mt-auto pt-2 border-t border-border text-xs text-muted-foreground flex-wrap">
                  <span className="flex items-center gap-1 truncate">
                    <User className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{article.created_by_name ?? "Desconocido"}</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Eye className="h-3.5 w-3.5" />
                    {article.view_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <ThumbsUp className="h-3.5 w-3.5" />
                    {article.helpful_count}
                  </span>
                </div>
              </Link>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                aria-label="Página anterior"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
                const isNearCurrent =
                  page === 1 || page === totalPages ||
                  Math.abs(page - currentPage) <= 1;
                const isEllipsisBefore = page === 2 && currentPage > 3;
                const isEllipsisAfter = page === totalPages - 1 && currentPage < totalPages - 2;

                if (!isNearCurrent) return null;
                if (isEllipsisBefore || isEllipsisAfter) {
                  return (
                    <span key={page} className="px-1 text-muted-foreground text-sm select-none">…</span>
                  );
                }
                return (
                  <button
                    key={page}
                    type="button"
                    onClick={() => setCurrentPage(page)}
                    className={`min-w-[2rem] h-8 px-2 rounded-md text-sm transition-colors ${
                      currentPage === page
                        ? "bg-primary text-primary-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted"
                    }`}
                  >
                    {page}
                  </button>
                );
              })}

              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                aria-label="Página siguiente"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

const STATUS_TABS: { label: string; value: KBStatus | "" }[] = [
  { label: "Todos", value: "" },
  { label: "Publicados", value: "published" },
  { label: "En revisión", value: "in_review" },
  { label: "Borradores", value: "draft" },
  { label: "Rechazados", value: "rejected" },
];

const VALID_STATUSES: KBStatus[] = ["draft", "in_review", "approved", "rejected", "published"];

function parseStatusParam(raw: string | null): KBStatus | "" {
  return raw && (VALID_STATUSES as string[]).includes(raw) ? (raw as KBStatus) : "";
}

export default function KBPage() {
  usePermissionGuard("knowledge_base", "read");
  const searchParams = useSearchParams();
  const initialTagSlug = searchParams.get("tag") ?? "";
  const initialStatus = parseStatusParam(searchParams.get("status"));

  const [filters, setFilters] = useState<Filter[]>([]);
  const [activeStatus, setActiveStatus] = useState<KBStatus | "">(initialStatus);
  const [activeTagSlug, setActiveTagSlug] = useState<string>(initialTagSlug);
  const { data: tags = [] } = useKBTags();

  // Sincroniza si los query params cambian — útil cuando el usuario llega vía
  // links externos ("?tag=bug") o desde el banner de pendientes ("?status=in_review")
  // sin desmontar el componente.
  useEffect(() => {
    setActiveTagSlug(searchParams.get("tag") ?? "");
    setActiveStatus(parseStatusParam(searchParams.get("status")));
  }, [searchParams]);

  const { data: articles = [], isLoading } = useKBArticles(
    activeStatus || undefined,
    activeTagSlug || undefined,
  );

  const scoredArticles = useMemo(
    () => searchArticles(articles, filters),
    [articles, filters],
  );

  return (
    <div className="flex flex-col gap-5">
      <PendingReviewBanner />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Base de Conocimiento</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${scoredArticles.length} artículo${scoredArticles.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Link href="/kb/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            Nuevo artículo
          </Button>
        </Link>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <KBSearchPanel
          filters={filters}
          onFiltersChange={setFilters}
          className="sm:w-96"
        />
        <div className="flex items-center gap-1 overflow-x-auto">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveStatus(tab.value)}
              className={`px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition-colors ${
                activeStatus === tab.value
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {tags.length > 0 && (
        <div className="flex items-center gap-1 overflow-x-auto">
          <button
            type="button"
            onClick={() => setActiveTagSlug("")}
            className={`px-2.5 py-1 rounded-md text-xs whitespace-nowrap transition-colors ${
              activeTagSlug === ""
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            Todos los tags
          </button>
          {tags.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTagSlug(t.slug)}
              className={`px-2.5 py-1 rounded-md text-xs whitespace-nowrap transition-colors ${
                activeTagSlug === t.slug
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {scoredArticles.length === 0 && (
            <div className="col-span-full rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
              <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">
                {filters.length === 0
                  ? "No hay artículos que mostrar"
                  : "0 resultados — refina con menos filtros o desactiva el modo exacto"}
              </p>
            </div>
          )}
          {scoredArticles.map(({ article, score, matched }) => (
            <Link
              key={article.id}
              href={`/kb/${article.id}`}
              className="rounded-lg border border-border bg-card p-3.5 hover:border-primary/30 hover:shadow-sm transition-all duration-150 flex flex-col gap-2"
            >
              {score != null && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium",
                      scoreBand(score) === "excelente" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
                      scoreBand(score) === "muy-bueno" && "bg-sky-500/10 text-sky-700 dark:text-sky-300",
                      scoreBand(score) === "bueno" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
                      scoreBand(score) === "parcial" && "bg-slate-500/10 text-slate-600 dark:text-slate-400",
                    )}
                  >
                    {Math.round(score)}%
                  </span>
                  {matched.map((m) => (
                    <span
                      key={m}
                      className={cn(
                        "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold",
                        m === "T" && "bg-blue-500/10 text-blue-700 dark:text-blue-300",
                        m === "C" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
                        m === "E" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
                        m === "CA" && "bg-purple-500/10 text-purple-700 dark:text-purple-300",
                      )}
                      title={
                        m === "T" ? "Coincide en Título" :
                        m === "C" ? "Coincide en Contenido" :
                        m === "E" ? "Coincide en Etiquetas" :
                        "Coincide en Casos asociados"
                      }
                    >
                      {m}
                    </span>
                  ))}
                </div>
              )}
              {/* Status + versión: línea pequeña arriba (info de estado del documento) */}
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge status={article.status} />
                <span className="text-xs text-muted-foreground">v{article.version}</span>
              </div>

              {/* 1. Título */}
              <h3 className="font-semibold text-foreground hover:text-primary transition-colors line-clamp-2">
                {article.title}
              </h3>

              {/* 2. Tipo de documento + 3. Visibilidad */}
              <div className="flex items-center gap-2 flex-wrap">
                <DocumentTypeBadge type={article.document_type} />
                <VisibilityBadge visibility={article.visibility} />
              </div>

              {/* 4. Tags */}
              {article.tags && article.tags.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  {article.tags.map((t) => (
                    <span
                      key={t.id}
                      className="inline-flex items-center rounded-md bg-primary/10 text-primary text-xs px-2 py-0.5"
                    >
                      {t.name}
                    </span>
                  ))}
                </div>
              )}

              {/* 5. Creador + stats — fila final, empuja al fondo del card */}
              <div className="flex items-center gap-3 mt-auto pt-2 border-t border-border text-xs text-muted-foreground flex-wrap">
                <span className="flex items-center gap-1 truncate">
                  <User className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{article.created_by_name ?? "Desconocido"}</span>
                </span>
                <span className="flex items-center gap-1">
                  <Eye className="h-3.5 w-3.5" />
                  {article.view_count}
                </span>
                <span className="flex items-center gap-1">
                  <ThumbsUp className="h-3.5 w-3.5" />
                  {article.helpful_count}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
