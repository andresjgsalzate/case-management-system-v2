"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, AlertTriangle } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { Spinner } from "@/components/atoms/Spinner";
import { KBEditor } from "@/components/organisms/KBEditor";
import { TagMultiSelect } from "@/components/molecules/TagMultiSelect";
import { DocumentTypeSelect } from "@/components/molecules/DocumentTypeSelect";
import { VisibilitySelect } from "@/components/molecules/VisibilitySelect";
import { RelatedCasesSection } from "@/components/organisms/RelatedCasesSection";
import { useKBArticle, useUpdateKBArticle } from "@/hooks/useKB";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import type { KBVisibility } from "@/lib/types";

export default function EditKBArticlePage({ params }: { params: { id: string } }) {
  usePermissionGuard("knowledge_base", "create");
  const router = useRouter();
  const { data: article, isLoading } = useKBArticle(params.id);
  const updateArticle = useUpdateKBArticle(params.id);

  const [title, setTitle] = useState("");
  const [editorValue, setEditorValue] = useState<{
    content_json: Record<string, unknown>;
    content_text: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [documentTypeId, setDocumentTypeId] = useState<string | null>(null);
  const [visibility, setVisibility] = useState<KBVisibility>("private");

  useEffect(() => {
    if (article) {
      setTitle(article.title);
      setTagIds(article.tags?.map((t) => t.id) ?? []);
      setDocumentTypeId(article.document_type_id ?? null);
      setVisibility(article.visibility);
    }
  }, [article]);

  // Solo bloquear edición si el artículo está en revisión (race con un revisor).
  // Los artículos approved/published se pueden editar y vuelven a draft al guardar.
  useEffect(() => {
    if (article && article.status === "in_review") {
      router.replace(`/kb/${params.id}`);
    }
  }, [article, params.id, router]);

  const willRevertToDraft =
    article?.status === "published" || article?.status === "approved";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("El título es obligatorio"); return; }

    try {
      await updateArticle.mutateAsync({
        title: title.trim(),
        tag_ids: tagIds,
        document_type_id: documentTypeId,
        visibility,
        ...(editorValue && {
          content_json: editorValue.content_json,
          content_text: editorValue.content_text,
        }),
      });
      router.push(`/kb/${params.id}`);
    } catch {
      setError("Error al guardar los cambios.");
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!article) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
        <p>Artículo no encontrado.</p>
        <Link href="/kb" className="text-primary text-sm hover:underline">Volver a KB</Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link
          href={`/kb/${params.id}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Volver al artículo
        </Link>
        <h1 className="text-xl font-semibold">Editar artículo</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Editá el contenido. Los cambios crean una nueva versión en el historial.
        </p>
      </div>

      {willRevertToDraft && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-700/60 dark:bg-amber-950/40 p-4"
        >
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
              Este artículo está {article.status === "published" ? "publicado" : "aprobado"}.
            </p>
            <p className="text-sm text-amber-800 dark:text-amber-200/90">
              Si guardás los cambios, volverá al estado <strong>borrador</strong> y deberá
              pasar nuevamente por revisión y aprobación antes de re-publicarse. La versión
              actual queda guardada en el historial.
            </p>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card p-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <FormField label="Título" htmlFor="kb-title" required>
            <Input
              id="kb-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Título del artículo…"
            />
          </FormField>

          {/* Tags justo debajo del título */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Tags</label>
            <TagMultiSelect value={tagIds} onChange={setTagIds} />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Tipo de documento</label>
            <DocumentTypeSelect value={documentTypeId} onChange={setDocumentTypeId} />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Visibilidad</label>
            <VisibilitySelect
              value={visibility}
              onChange={setVisibility}
              pending={article.pending_visibility}
            />
          </div>

          {/* Casos relacionados — editable solo aquí, en /edit */}
          <div className="flex flex-col gap-1.5 pt-2 border-t border-border">
            <RelatedCasesSection articleId={params.id} canEdit={true} />
          </div>

          <FormField label="Contenido" htmlFor="kb-content" required>
            <KBEditor
              initialContent={article.content_json}
              onChange={setEditorValue}
            />
          </FormField>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-3">
            <Button type="submit" loading={updateArticle.isPending}>
              {willRevertToDraft ? "Guardar y volver a borrador" : "Guardar cambios"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push(`/kb/${params.id}`)}
            >
              Cancelar
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
