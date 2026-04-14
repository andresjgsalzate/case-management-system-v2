"use client";

import Link from "next/link";
import { ChevronLeft, Eye, ThumbsUp, ThumbsDown, Calendar } from "lucide-react";
import { useKBArticle } from "@/hooks/useKB";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";

export default function KBArticlePage({ params }: { params: { id: string } }) {
  const { data: article, isLoading, error } = useKBArticle(params.id);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
        <p>Artículo no encontrado.</p>
        <Link href="/kb" className="text-primary text-sm hover:underline">Volver a KB</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <Link
        href="/kb"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Base de conocimiento
      </Link>

      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-start gap-3 mb-4">
          <StatusBadge status={article.status} />
          <span className="text-xs text-muted-foreground">Versión {article.version}</span>
        </div>
        <h1 className="text-2xl font-bold text-foreground mb-4">{article.title}</h1>

        <div className="flex items-center gap-5 text-xs text-muted-foreground pb-4 mb-6 border-b border-border">
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {formatDate(article.updated_at)}
          </span>
          <span className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" />
            {article.view_count} vistas
          </span>
          <span className="flex items-center gap-1 text-emerald-600">
            <ThumbsUp className="h-3.5 w-3.5" />
            {article.helpful_count}
          </span>
          <span className="flex items-center gap-1 text-red-500">
            <ThumbsDown className="h-3.5 w-3.5" />
            {article.not_helpful_count}
          </span>
        </div>

        {/* Article content */}
        <div className="prose prose-sm max-w-none text-foreground">
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
            {article.content_text}
          </p>
        </div>
      </div>
    </div>
  );
}
