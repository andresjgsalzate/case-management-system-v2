"use client";

import { useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import {
  useDocumentTypes,
  useCreateDocumentType,
  useUpdateDocumentType,
  useDeleteDocumentType,
} from "@/hooks/useKB";
import { DocumentTypeBadge } from "@/components/molecules/DocumentTypeBadge";
import type { KBDocumentType } from "@/lib/types";

interface FormState {
  code: string;
  name: string;
  icon: string;
  color: string;
  sort_order: number;
}

const EMPTY_FORM: FormState = {
  code: "",
  name: "",
  icon: "FileText",
  color: "#3B82F6",
  sort_order: 0,
};

export default function DocumentTypesAdminPage() {
  usePermissionGuard("document_types", "update");
  const { data: types = [], isLoading } = useDocumentTypes(true);
  const createMut = useCreateDocumentType();
  const updateMut = useUpdateDocumentType();
  const deleteMut = useDeleteDocumentType();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setShowForm(true);
  }

  function openEdit(t: KBDocumentType) {
    setForm({
      code: t.code,
      name: t.name,
      icon: t.icon,
      color: t.color,
      sort_order: t.sort_order,
    });
    setEditingId(t.id);
    setShowForm(true);
  }

  async function submit() {
    if (editingId) {
      await updateMut.mutateAsync({ id: editingId, ...form });
    } else {
      await createMut.mutateAsync(form);
    }
    setShowForm(false);
  }

  async function remove(t: KBDocumentType) {
    if (!confirm(`Desactivar tipo "${t.name}"? Los artículos existentes lo mantienen.`)) return;
    await deleteMut.mutateAsync(t.id);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Tipos de documento</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configura los tipos de artículos del KB
          </p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Nuevo tipo
        </Button>
      </div>

      {isLoading && <Spinner size="lg" />}

      {!isLoading && (
        <div className="rounded-lg border border-border bg-card divide-y divide-border">
          {types.length === 0 && (
            <p className="p-8 text-center text-sm text-muted-foreground">
              No hay tipos configurados
            </p>
          )}
          {types.map((t) => (
            <div
              key={t.id}
              className={`flex items-center justify-between p-4 ${
                !t.is_active ? "opacity-50" : ""
              }`}
            >
              <div className="flex items-center gap-3">
                <DocumentTypeBadge type={t} size="md" />
                <div>
                  <p className="text-sm font-medium">{t.name}</p>
                  <p className="text-xs text-muted-foreground">
                    code: {t.code} · orden: {t.sort_order}
                    {!t.is_active && " · INACTIVO"}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => openEdit(t)}>
                  <Pencil className="h-3 w-3" />
                </Button>
                {t.is_active && (
                  <Button size="sm" variant="destructive" onClick={() => remove(t)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-card rounded-lg border border-border p-6 w-full max-w-md shadow-xl flex flex-col gap-3">
            <h2 className="text-base font-semibold">
              {editingId ? "Editar tipo" : "Nuevo tipo"}
            </h2>

            <label className="flex flex-col gap-1 text-sm">
              Código (único)
              <input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                disabled={!!editingId}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm disabled:opacity-50"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Nombre
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Icono (nombre Lucide, p.ej. BookOpen)
              <input
                value={form.icon}
                onChange={(e) => setForm({ ...form, icon: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Color (hex)
              <input
                type="color"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                className="h-9 w-full rounded-md border border-border"
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              Orden
              <input
                type="number"
                value={form.sort_order}
                onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm"
              />
            </label>

            <div className="flex gap-3 justify-end mt-2">
              <Button variant="outline" onClick={() => setShowForm(false)}>
                Cancelar
              </Button>
              <Button
                onClick={submit}
                loading={createMut.isPending || updateMut.isPending}
                disabled={!form.code || !form.name || !form.icon}
              >
                Guardar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
