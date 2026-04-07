"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Input } from "@/components/atoms/Input";
import { FormField } from "@/components/molecules/FormField";
import { useCreateKBArticle } from "@/hooks/useKB";

export default function NewKBArticlePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const createArticle = useCreateKBArticle();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("El título es obligatorio"); return; }
    if (!content.trim()) { setError("El contenido no puede estar vacío"); return; }

    try {
      const article = await createArticle.mutateAsync({
        title: title.trim(),
        content_json: { type: "doc", content: [{ type: "paragraph", text: content }] },
        content_text: content.trim(),
      });
      router.push(`/kb/${article.id}`);
    } catch {
      setError("Error al crear el artículo.");
    }
  }

  return (
    <div className="flex flex-col gap-5 max-w-2xl">
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
            <textarea
              id="kb-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Escribe el contenido del artículo…"
              rows={12}
              className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
            />
          </FormField>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-3">
            <Button type="submit" loading={createArticle.isPending}>Crear borrador</Button>
            <Button type="button" variant="outline" onClick={() => router.back()}>Cancelar</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
