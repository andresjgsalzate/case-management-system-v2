"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";
import { useCaseKBArticles } from "@/hooks/useKB";
import { DocumentTypeBadge } from "@/components/molecules/DocumentTypeBadge";
import { Spinner } from "@/components/atoms/Spinner";

interface RelatedKBArticlesSectionProps {
  caseId: string;
}

export function RelatedKBArticlesSection({ caseId }: RelatedKBArticlesSectionProps) {
  const { data: articles = [], isLoading } = useCaseKBArticles(caseId);

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
        <BookOpen className="h-4 w-4 text-muted-foreground" />
        Documentos KB relacionados
      </h2>

      {isLoading && <Spinner size="sm" />}

      {!isLoading && articles.length === 0 && (
        <p className="text-xs text-muted-foreground">Sin documentos KB asociados.</p>
      )}

      {articles.length > 0 && (
        <ul className="flex flex-col gap-1">
          {articles.map((a) => (
            <li key={a.id}>
              <Link
                href={`/kb/${a.id}`}
                className="flex items-center gap-2 rounded-md border border-border bg-card hover:bg-muted/40 p-2 transition-colors"
              >
                {a.document_type && (
                  <DocumentTypeBadge type={a.document_type} size="sm" />
                )}
                <span className="text-sm font-medium text-foreground truncate">
                  {a.title}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
