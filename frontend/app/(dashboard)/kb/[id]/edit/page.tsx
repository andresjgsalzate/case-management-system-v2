"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { Spinner } from "@/components/atoms/Spinner";
import { KBEditor } from "@/components/organisms/KBEditor";
import { TagMultiSelect } from "@/components/molecules/TagMultiSelect";
import { DocumentTypeSelect } from "@/components/molecules/DocumentTypeSelect";
import { useKBArticle, useUpdateKBArticle } from "@/hooks/useKB";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";

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

  useEffect(() => {
    if (article) {
      setTitle(article.title);
      setTagIds(article.tags?.map((t) => t.id) ?? []);
      setDocumentTypeId(article.document_type_id ?? null);
    }
  }, [article]);

  // Redirigir si el artículo no es editable
  useEffect(() => {
    if (article && article.status !== "draft" && article.status !== "rejected") {
      router.replace(`/kb/${params.id}`);
    }
  }, [article, params.id, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("El título es obligatorio"); return; }

    try {
      await updateArticle.mutateAsync({
        title: title.trim(),
        tag_ids: tagIds,
        document_type_id: documentTypeId,
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
          Solo se pueden editar borradores y artículos rechazados.
        </p>
      </div>

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

          <FormField label="Contenido" htmlFor="kb-content" required>
            <KBEditor
              initialContent={article.content_json}
              onChange={setEditorValue}
            />
          </FormField>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Tipo de documento</label>
            <DocumentTypeSelect value={documentTypeId} onChange={setDocumentTypeId} />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Tags</label>
            <TagMultiSelect value={tagIds} onChange={setTagIds} />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-3">
            <Button type="submit" loading={updateArticle.isPending}>
              Guardar cambios
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
