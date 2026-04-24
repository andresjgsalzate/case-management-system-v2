"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, X, Briefcase } from "lucide-react";
import {
  useArticleCases,
  useLinkCaseToArticle,
  useUnlinkCaseFromArticle,
} from "@/hooks/useKB";
import { CasePicker } from "@/components/molecules/CasePicker";
import { Spinner } from "@/components/atoms/Spinner";

interface RelatedCasesSectionProps {
  articleId: string;
  canEdit: boolean;
}

export function RelatedCasesSection({ articleId, canEdit }: RelatedCasesSectionProps) {
  const { data: cases = [], isLoading } = useArticleCases(articleId);
  const link = useLinkCaseToArticle(articleId);
  const unlink = useUnlinkCaseFromArticle(articleId);
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <Briefcase className="h-4 w-4 text-muted-foreground" />
          Casos relacionados
        </h2>
        {canEdit && !pickerOpen && (
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Plus className="h-3.5 w-3.5" />
            Agregar caso
          </button>
        )}
      </div>

      {isLoading && <Spinner size="sm" />}

      {!isLoading && cases.length === 0 && !pickerOpen && (
        <p className="text-xs text-muted-foreground">Sin casos asociados.</p>
      )}

      {cases.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {cases.map((c) => {
            const chip = (
              <span className="font-medium">{c.case_number}</span>
            );
            const body = c.can_access ? (
              <Link
                href={`/cases/${c.case_id}`}
                className="inline-flex items-center gap-1 rounded-md bg-muted/70 hover:bg-muted text-foreground text-xs px-2 py-0.5 transition-colors"
                title={c.case_title}
              >
                {chip}
              </Link>
            ) : (
              <span
                className="inline-flex items-center gap-1 rounded-md bg-muted/40 text-muted-foreground text-xs px-2 py-0.5 cursor-default"
                title="Sin acceso al caso"
              >
                {chip}
              </span>
            );
            return (
              <span key={c.case_id} className="inline-flex items-center gap-0.5">
                {body}
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => unlink.mutate(c.case_id)}
                    className="h-5 w-5 inline-flex items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                    title="Quitar"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </span>
            );
          })}
        </div>
      )}

      {pickerOpen && (
        <CasePicker
          excludeIds={cases.map((c) => c.case_id)}
          onSelect={async (caseId) => {
            await link.mutateAsync(caseId);
            setPickerOpen(false);
          }}
          onCancel={() => setPickerOpen(false)}
        />
      )}
    </section>
  );
}
