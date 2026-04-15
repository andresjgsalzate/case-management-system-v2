"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Tag, Plus, Pencil, Trash2, X, FolderOpen, Check } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { SearchBar } from "@/components/molecules/SearchBar";
import { Spinner } from "@/components/atoms/Spinner";
import { cn } from "@/lib/utils";
import type { Disposition, DispositionCategory, ApiResponse } from "@/lib/types";

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useCategories() {
  return useQuery<DispositionCategory[]>({
    queryKey: ["disposition-categories"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<DispositionCategory[]>>("/dispositions/categories");
      return data.data ?? [];
    },
  });
}

function useDispositions(categoryId?: string, search?: string) {
  return useQuery<Disposition[]>({
    queryKey: ["dispositions", categoryId, search],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (search) params.q = search;
      else if (categoryId) params.category_id = categoryId;
      const { data } = await apiClient.get<ApiResponse<Disposition[]>>("/dispositions", { params });
      return data.data ?? [];
    },
  });
}

function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiClient.post("/dispositions/categories", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disposition-categories"] }),
  });
}

function useCreateDisposition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { category_id: string; title: string; content: string }) =>
      apiClient.post("/dispositions", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispositions"] }),
  });
}

function useUpdateDisposition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; title?: string; content?: string }) =>
      apiClient.patch(`/dispositions/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispositions"] }),
  });
}

function useDeleteDisposition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/dispositions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispositions"] }),
  });
}

// ── Category modal ────────────────────────────────────────────────────────────

function CategoryModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useCreateCategory();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync({ name: name.trim(), description: description.trim() || undefined });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-sm mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">Nueva categoría</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-5 py-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Nombre *</label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ej: Respuestas técnicas"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Descripción</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Opcional"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors">
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!name.trim() || create.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {create.isPending ? <Spinner size="sm" /> : <Check className="h-3.5 w-3.5" />}
              Crear
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Disposition modal ─────────────────────────────────────────────────────────

function DispositionModal({
  categories,
  editing,
  onClose,
}: {
  categories: DispositionCategory[];
  editing?: Disposition;
  onClose: () => void;
}) {
  const [categoryId, setCategoryId] = useState(editing?.category_id ?? categories[0]?.id ?? "");
  const [title, setTitle] = useState(editing?.title ?? "");
  const [content, setContent] = useState(editing?.content ?? "");

  const create = useCreateDisposition();
  const update = useUpdateDisposition();
  const isPending = create.isPending || update.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    if (editing) {
      await update.mutateAsync({ id: editing.id, title: title.trim(), content: content.trim() });
    } else {
      await create.mutateAsync({ category_id: categoryId, title: title.trim(), content: content.trim() });
    }
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">
            {editing ? "Editar disposición" : "Nueva disposición"}
          </h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-5 py-4">
          {!editing && (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground">Categoría *</label>
              {categories.length === 0 ? (
                <p className="text-xs text-amber-600">Crea una categoría primero.</p>
              ) : (
                <select
                  value={categoryId}
                  onChange={e => setCategoryId(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {categories.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              )}
            </div>
          )}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Título *</label>
            <input
              autoFocus
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Ej: Cierre por resolución"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Contenido *</label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Escribe la respuesta o plantilla predefinida…"
              rows={5}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors">
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!title.trim() || !content.trim() || (!editing && !categoryId) || isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {isPending ? <Spinner size="sm" /> : <Check className="h-3.5 w-3.5" />}
              {editing ? "Guardar cambios" : "Crear disposición"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DispositionsPage() {
  const [search, setSearch] = useState("");
  const [activeCategoryId, setActiveCategoryId] = useState<string | undefined>(undefined);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showDispositionModal, setShowDispositionModal] = useState(false);
  const [editing, setEditing] = useState<Disposition | undefined>(undefined);

  const { data: categories = [] } = useCategories();
  const { data: dispositions = [], isLoading } = useDispositions(
    search ? undefined : activeCategoryId,
    search || undefined,
  );
  const deleteDisposition = useDeleteDisposition();

  function openEdit(d: Disposition) {
    setEditing(d);
    setShowDispositionModal(true);
  }

  function closeDispositionModal() {
    setShowDispositionModal(false);
    setEditing(undefined);
  }

  const categoryName = (id: string) =>
    categories.find(c => c.id === id)?.name ?? "—";

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Disposiciones</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Respuestas y plantillas predefinidas para casos
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowCategoryModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted text-muted-foreground transition-colors"
          >
            <FolderOpen className="h-3.5 w-3.5" />
            Nueva categoría
          </button>
          <button
            type="button"
            onClick={() => { setEditing(undefined); setShowDispositionModal(true); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Nueva disposición
          </button>
        </div>
      </div>

      {/* Category filter chips */}
      {categories.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveCategoryId(undefined)}
            className={cn(
              "px-3 py-1 text-xs rounded-full border transition-colors",
              !activeCategoryId
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
            )}
          >
            Todas
          </button>
          {categories.map(c => (
            <button
              key={c.id}
              type="button"
              onClick={() => setActiveCategoryId(c.id === activeCategoryId ? undefined : c.id)}
              className={cn(
                "px-3 py-1 text-xs rounded-full border transition-colors",
                activeCategoryId === c.id
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
              )}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      {/* Search */}
      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Buscar disposición…"
        className="max-w-sm"
      />

      {/* List */}
      {isLoading && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {!isLoading && dispositions.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
          <Tag className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">
            {search ? "Sin resultados para esa búsqueda" : "No hay disposiciones. Crea una para empezar."}
          </p>
        </div>
      )}

      <div className="grid gap-2">
        {dispositions.map((d) => (
          <div
            key={d.id}
            className="rounded-lg border border-border bg-card p-4 flex items-start gap-3 hover:border-primary/30 transition-colors group"
          >
            <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
              <Tag className="h-4 w-4 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">{d.title}</p>
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{d.content}</p>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-xs text-muted-foreground">
                  Usada {d.usage_count} {d.usage_count !== 1 ? "veces" : "vez"}
                </span>
                {!search && (
                  <span className="text-xs text-muted-foreground opacity-60">
                    {categoryName(d.category_id)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                onClick={() => openEdit(d)}
                title="Editar"
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => deleteDisposition.mutate(d.id)}
                title="Eliminar"
                className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Modals */}
      {showCategoryModal && (
        <CategoryModal onClose={() => setShowCategoryModal(false)} />
      )}
      {showDispositionModal && (
        <DispositionModal
          categories={categories}
          editing={editing}
          onClose={closeDispositionModal}
        />
      )}
    </div>
  );
}
