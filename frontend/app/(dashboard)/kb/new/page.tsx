"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { KBEditor } from "@/components/organisms/KBEditor";
import { useCreateKBArticle } from "@/hooks/useKB";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";

export default function NewKBArticlePage() {
  usePermissionGuard("knowledge_base", "create");
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [editorValue, setEditorValue] = useState<{
    content_json: Record<string, unknown>;
    content_text: string;
  } | null>(null);
  const [error, setError] = useState("");
  const createArticle = useCreateKBArticle();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("El título es obligatorio"); return; }
    if (!editorValue?.content_text?.trim()) { setError("El contenido no puede estar vacío"); return; }

    try {
      const article = await createArticle.mutateAsync({
        title: title.trim(),
        content_json: editorValue.content_json,
        content_text: editorValue.content_text,
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
            <KBEditor onChange={setEditorValue} />
          </FormField>

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
