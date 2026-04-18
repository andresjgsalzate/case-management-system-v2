"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, BookOpen, Eye, ThumbsUp } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { SearchBar } from "@/components/molecules/SearchBar";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { DocumentTypeBadge } from "@/components/molecules/DocumentTypeBadge";
import { Spinner } from "@/components/atoms/Spinner";
import { useKBArticles, useKBTags } from "@/hooks/useKB";
import { PendingReviewBanner } from "@/components/organisms/PendingReviewBanner";
import { formatDate, truncate } from "@/lib/utils";
import type { KBStatus } from "@/lib/types";

const STATUS_TABS: { label: string; value: KBStatus | "" }[] = [
  { label: "Todos", value: "" },
  { label: "Publicados", value: "published" },
  { label: "En revisión", value: "in_review" },
  { label: "Borradores", value: "draft" },
  { label: "Rechazados", value: "rejected" },
];

export default function KBPage() {
  usePermissionGuard("knowledge_base", "read");
  const [search, setSearch] = useState("");
  const [activeStatus, setActiveStatus] = useState<KBStatus | "">("");
  const [activeTagSlug, setActiveTagSlug] = useState<string>("");
  const { data: tags = [] } = useKBTags();

  const { data: articles = [], isLoading } = useKBArticles(
    activeStatus || undefined,
    activeTagSlug || undefined,
  );

  const filtered = search.trim()
    ? articles.filter((a) =>
        a.title.toLowerCase().includes(search.toLowerCase()) ||
        a.content_text.toLowerCase().includes(search.toLowerCase())
      )
    : articles;

  return (
    <div className="flex flex-col gap-5">
      <PendingReviewBanner />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Base de Conocimiento</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${filtered.length} artículo${filtered.length !== 1 ? "s" : ""}`}
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
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar artículos…"
          className="sm:w-72"
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
        <div className="grid gap-3">
          {filtered.length === 0 && (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
              <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No hay artículos que mostrar</p>
            </div>
          )}
          {filtered.map((article) => (
            <Link
              key={article.id}
              href={`/kb/${article.id}`}
              className="rounded-lg border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all duration-150 block"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <StatusBadge status={article.status} />
                    <DocumentTypeBadge type={article.document_type} />
                    <span className="text-xs text-muted-foreground">v{article.version}</span>
                  </div>
                  <h3 className="font-medium text-foreground hover:text-primary transition-colors">
                    {article.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                    {truncate(article.content_text, 150)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Eye className="h-3.5 w-3.5" />
                  {article.view_count}
                </span>
                <span className="flex items-center gap-1">
                  <ThumbsUp className="h-3.5 w-3.5" />
                  {article.helpful_count}
                </span>
                <span>{formatDate(article.updated_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
