"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, FileText } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { KBEditor } from "@/components/organisms/KBEditor";
import { TagMultiSelect } from "@/components/molecules/TagMultiSelect";
import { DocumentTypeSelect } from "@/components/molecules/DocumentTypeSelect";
import { useCreateKBArticle } from "@/hooks/useKB";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { DOCUMENTATION_TEMPLATE, templateToPlainText } from "@/lib/kb-templates";

export default function NewKBArticlePage() {
  usePermissionGuard("knowledge_base", "create");
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [editorValue, setEditorValue] = useState<{
    content_json: Record<string, unknown>;
    content_text: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [documentTypeId, setDocumentTypeId] = useState<string | null>(null);
  const [editorKey, setEditorKey] = useState(0);
  const [editorInitial, setEditorInitial] = useState<
    Record<string, unknown> | undefined
  >(undefined);
  const createArticle = useCreateKBArticle();

  function applyTemplate() {
    const contentJson = { blocks: DOCUMENTATION_TEMPLATE };
    const contentText = templateToPlainText();
    setEditorInitial(contentJson);
    setEditorValue({ content_json: contentJson, content_text: contentText });
    setEditorKey((k) => k + 1);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("El título es obligatorio"); return; }
    if (!editorValue?.content_text?.trim()) { setError("El contenido no puede estar vacío"); return; }

    try {
      const article = await createArticle.mutateAsync({
        title: title.trim(),
        content_json: editorValue.content_json,
        content_text: editorValue.content_text,
        tag_ids: tagIds,
        document_type_id: documentTypeId,
      });
      router.push(`/kb/${article!.id}`);
    } catch {
      setError("Error al crear el artículo.");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link
          href="/kb"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Base de conocimiento
        </Link>
        <h1 className="text-xl font-semibold">Nuevo artículo</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Los artículos nuevos se crean como borrador.
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
            <div className="flex flex-col gap-2">
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={applyTemplate}
                >
                  <FileText className="h-4 w-4 mr-1" />
                  Usar plantilla
                </Button>
              </div>
              <KBEditor
                key={editorKey}
                initialContent={editorInitial}
                onChange={setEditorValue}
              />
            </div>
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
            <Button type="submit" loading={createArticle.isPending}>
              Crear borrador
            </Button>
            <Button type="button" variant="outline" onClick={() => router.back()}>
              Cancelar
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
