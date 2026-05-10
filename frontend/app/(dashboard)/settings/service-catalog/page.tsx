"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, ChevronRight, ChevronDown, Package, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import {
  useServiceCategories,
  useServiceItems,
  useCreateServiceCategory,
  useUpdateServiceCategory,
  useDeleteServiceCategory,
  useDeleteServiceItem,
} from "@/hooks/useServiceCatalog";
import type { ServiceCatalogCategory } from "@/lib/types";
import { CategoryModal } from "@/components/organisms/ServiceCatalog/CategoryModal";
import { ItemModal } from "@/components/organisms/ServiceCatalog/ItemModal";

export default function ServiceCatalogPage() {
  usePermissionGuard("service_catalog", "read");
  const confirm = useConfirm();

  const { data: categories = [], isLoading } = useServiceCategories();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [catModal, setCatModal] = useState<{ mode: "create" | "edit"; category?: ServiceCatalogCategory } | null>(null);
  const [itemModal, setItemModal] = useState<{ categoryId: string } | null>(null);

  const deleteCat = useDeleteServiceCategory();

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleDeleteCat(cat: ServiceCatalogCategory) {
    const ok = await confirm({
      title: `¿Eliminar categoría "${cat.name}"?`,
      description: cat.item_count > 0
        ? "Tiene ítems dentro; primero deberás eliminarlos o moverlos."
        : "La categoría quedará eliminada permanentemente.",
    });
    if (!ok) return;
    try {
      await deleteCat.mutateAsync(cat.id);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      alert(e?.response?.data?.message ?? "No se pudo eliminar");
    }
  }

  if (isLoading) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Catálogo de servicios</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Define categorías, tipos de solicitud y campos personalizados por cada tipo.
          </p>
        </div>
        <Button size="sm" onClick={() => setCatModal({ mode: "create" })}>
          <Plus className="h-4 w-4" />
          Nueva categoría
        </Button>
      </div>

      {categories.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-10 text-center text-muted-foreground">
          <Package className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No hay categorías creadas aún.</p>
          <p className="text-xs mt-1">Haz clic en &ldquo;Nueva categoría&rdquo; para empezar.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-card overflow-hidden divide-y divide-border">
          {categories.map((cat) => (
            <CategoryRow
              key={cat.id}
              category={cat}
              expanded={expanded.has(cat.id)}
              onToggle={() => toggle(cat.id)}
              onEdit={() => setCatModal({ mode: "edit", category: cat })}
              onDelete={() => handleDeleteCat(cat)}
              onAddItem={() => setItemModal({ categoryId: cat.id })}
            />
          ))}
        </div>
      )}

      {catModal && (
        <CategoryModal
          mode={catModal.mode}
          category={catModal.category}
          onClose={() => setCatModal(null)}
          onCreated={(created) => {
            // Expandir la categoría recién creada para que el usuario vea
            // dónde caen los próximos ítems
            setExpanded((prev) => new Set(prev).add(created.id));
          }}
        />
      )}
      {itemModal && (
        <ItemModal
          mode="create"
          defaultCategoryId={itemModal.categoryId}
          onClose={() => setItemModal(null)}
        />
      )}
    </div>
  );
}

// ── Category row ───────────────────────────────────────────────────────────────

function CategoryRow({
  category,
  expanded,
  onToggle,
  onEdit,
  onDelete,
  onAddItem,
}: {
  category: ServiceCatalogCategory;
  expanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onAddItem: () => void;
}) {
  return (
    <div>
      <div className="flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors">
        <button
          type="button"
          onClick={onToggle}
          className="text-muted-foreground hover:text-foreground shrink-0"
          aria-label="Expandir"
        >
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        <div
          className="h-7 w-7 rounded-md flex items-center justify-center shrink-0"
          style={{ backgroundColor: category.color ?? "#e2e8f0", color: "#fff" }}
        >
          <Package className="h-3.5 w-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{category.name}</p>
          {category.description && (
            <p className="text-xs text-muted-foreground truncate">{category.description}</p>
          )}
        </div>
        <span className="text-xs text-muted-foreground shrink-0 tabular-nums">
          {category.item_count} ítem{category.item_count !== 1 ? "s" : ""}
        </span>
        {!category.is_active && (
          <span className="text-[10px] uppercase rounded px-1.5 py-0.5 bg-muted text-muted-foreground">
            Inactiva
          </span>
        )}
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onEdit}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
            title="Editar"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-destructive"
            title="Eliminar"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {expanded && (
        <CategoryItems
          categoryId={category.id}
          onAddItem={onAddItem}
        />
      )}
    </div>
  );
}

// ── Items dentro de una categoría ──────────────────────────────────────────────

function CategoryItems({
  categoryId,
  onAddItem,
}: {
  categoryId: string;
  onAddItem: () => void;
}) {
  const confirm = useConfirm();
  const { data: items = [], isLoading } = useServiceItems(categoryId);
  const del = useDeleteServiceItem();

  async function handleDelete(id: string, name: string) {
    const ok = await confirm({
      title: `¿Eliminar "${name}"?`,
      description: "Si hay casos ligados a este ítem, no se podrá eliminar (desactívalo).",
    });
    if (!ok) return;
    try {
      await del.mutateAsync(id);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      alert(e?.response?.data?.message ?? "No se pudo eliminar");
    }
  }

  return (
    <div className="bg-muted/20 border-t border-border">
      {isLoading ? (
        <div className="px-12 py-4 text-xs text-muted-foreground">Cargando ítems…</div>
      ) : items.length === 0 ? (
        <div className="pl-12 pr-4 py-5 flex flex-col items-start gap-2">
          <p className="text-sm text-muted-foreground">
            Esta categoría aún no tiene <strong className="text-foreground">tipos de solicitud</strong>.
          </p>
          <p className="text-xs text-muted-foreground">
            Crea uno para configurar prioridad, equipo, nivel inicial y los campos del formulario.
          </p>
          <button
            type="button"
            onClick={onAddItem}
            className="mt-1 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Crear primer tipo de solicitud
          </button>
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <li key={item.id} className="flex items-center gap-3 pl-12 pr-4 py-2.5 hover:bg-muted/40 transition-colors">
              <Link
                href={`/settings/service-catalog/items/${item.id}`}
                className="flex-1 min-w-0"
              >
                <p className="text-sm text-foreground truncate hover:text-primary transition-colors">
                  {item.name}
                </p>
                {item.description && (
                  <p className="text-xs text-muted-foreground truncate">{item.description}</p>
                )}
              </Link>
              <span className="text-xs text-muted-foreground shrink-0">
                {item.field_count} campo{item.field_count !== 1 ? "s" : ""}
              </span>
              <span className="text-xs text-muted-foreground shrink-0">
                N{item.default_level}
              </span>
              {!item.is_active && (
                <span className="text-[10px] uppercase rounded px-1.5 py-0.5 bg-muted text-muted-foreground">
                  Inactivo
                </span>
              )}
              <button
                type="button"
                onClick={() => handleDelete(item.id, item.name)}
                className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-destructive shrink-0"
                title="Eliminar ítem"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* "+ Añadir ítem" abajo solo si ya hay alguno; si está vacío, el CTA grande lo cubre */}
      {items.length > 0 && (
        <div className="pl-12 pr-4 py-2 border-t border-border">
          <button
            type="button"
            onClick={onAddItem}
            className="text-xs text-primary hover:underline inline-flex items-center gap-1"
          >
            <Plus className="h-3 w-3" />
            Añadir ítem
          </button>
        </div>
      )}
    </div>
  );
}
