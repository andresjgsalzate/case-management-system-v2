"use client";

import { Plus, Star, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import {
  useAddCatalogMapping,
  useRemoveCatalogMapping,
  useSetDefaultCatalogMapping,
  useTaxonomyCatalogMappings,
} from "@/hooks/useSecurityTaxonomies";
import { useServiceItems } from "@/hooks/useServiceCatalog";
import type { TaxonomyCatalogMapping } from "@/lib/types";

interface Props {
  taxonomyId: string;
}

/** Edits the (taxonomy ↔ service_catalog_item) mappings.
 *
 * Each mapping carries a `priority_order` and an `is_default` flag. At most
 * one mapping per taxonomy can be default (enforced by partial unique index
 * `ux_taxonomy_default`). When a mapping is set as default, the backend
 * automatically clears the flag from the previous default.
 */
export function TaxonomyCatalogMappingsEditor({ taxonomyId }: Props) {
  const { data: mappings, isLoading: mappingsLoading } =
    useTaxonomyCatalogMappings(taxonomyId);
  const { data: items, isLoading: itemsLoading } = useServiceItems();
  const add = useAddCatalogMapping();
  const setDefault = useSetDefaultCatalogMapping();
  const remove = useRemoveCatalogMapping();

  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState("");
  const [priorityOrder, setPriorityOrder] = useState(0);
  const [setAsDefault, setSetAsDefault] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Item id → display name lookup so rows show human-readable names.
  const itemById = useMemo(() => {
    const m = new Map<string, { name: string; category_name?: string }>();
    for (const it of items ?? []) {
      m.set(it.id, {
        name: it.name,
        category_name: it.category_name ?? undefined,
      });
    }
    return m;
  }, [items]);

  // Filter out already-mapped items from the picker.
  const availableItems = useMemo(() => {
    const taken = new Set((mappings ?? []).map((m) => m.service_catalog_item_id));
    return (items ?? []).filter((it) => !taken.has(it.id));
  }, [items, mappings]);

  async function handleAdd() {
    setErrorMsg(null);
    if (!selectedItemId) {
      setErrorMsg("Selecciona un ítem del catálogo de servicios");
      return;
    }
    try {
      await add.mutateAsync({
        taxonomy_id: taxonomyId,
        payload: {
          service_catalog_item_id: selectedItemId,
          priority_order: priorityOrder,
          is_default: setAsDefault,
        },
      });
      setPickerOpen(false);
      setSelectedItemId("");
      setPriorityOrder(0);
      setSetAsDefault(false);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setErrorMsg(detail ?? "Error al agregar mapping");
    }
  }

  async function handleSetDefault(mapping: TaxonomyCatalogMapping) {
    if (mapping.is_default) return;
    await setDefault.mutateAsync({
      taxonomy_id: taxonomyId,
      mapping_id: mapping.id,
    });
  }

  async function handleRemove(mapping: TaxonomyCatalogMapping) {
    const itemName = itemById.get(mapping.service_catalog_item_id)?.name ?? mapping.service_catalog_item_id;
    if (!confirm(`¿Eliminar el mapping a "${itemName}"?`)) return;
    await remove.mutateAsync({
      taxonomy_id: taxonomyId,
      mapping_id: mapping.id,
    });
  }

  if (mappingsLoading) {
    return <p className="p-2 text-xs text-muted-foreground">Cargando…</p>;
  }

  return (
    <div className="space-y-2">
      <header className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase text-muted-foreground">
          Mapeos al catálogo de servicios
        </h4>
        {!pickerOpen && (
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            disabled={itemsLoading || availableItems.length === 0}
            className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Plus className="h-3 w-3" /> Agregar
          </button>
        )}
      </header>

      {pickerOpen && (
        <div className="space-y-2 rounded border bg-muted/30 p-2">
          {errorMsg && (
            <p className="text-xs text-red-600">{errorMsg}</p>
          )}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Ítem del catálogo</label>
            <select
              value={selectedItemId}
              onChange={(e) => setSelectedItemId(e.target.value)}
              className="rounded border bg-background p-1 text-xs"
              disabled={itemsLoading}
            >
              <option value="">— Selecciona —</option>
              {availableItems.map((it) => (
                <option key={it.id} value={it.id}>
                  {it.category_name ? `${it.category_name} · ` : ""}{it.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-muted-foreground">Prioridad</span>
              <input
                type="number"
                value={priorityOrder}
                onChange={(e) => setPriorityOrder(Number(e.target.value))}
                className="w-20 rounded border bg-background p-1 text-xs"
              />
            </label>
            <label className="flex items-center gap-1 text-xs">
              <input
                type="checkbox"
                checked={setAsDefault}
                onChange={(e) => setSetAsDefault(e.target.checked)}
              />
              Default
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => {
                setPickerOpen(false);
                setErrorMsg(null);
              }}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleAdd}
              disabled={add.isPending}
              className="rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {add.isPending ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      )}

      {mappings && mappings.length === 0 ? (
        <p className="rounded border border-dashed p-2 text-xs text-muted-foreground">
          Sin mapeos. Al menos uno (marcado como default) habilita la
          clasificación automática cuando un evento llega con tipo de servicio
          asociado.
        </p>
      ) : null}

      {mappings && mappings.length > 0 && (
        <ul className="space-y-1">
          {mappings.map((m) => {
            const item = itemById.get(m.service_catalog_item_id);
            return (
              <li
                key={m.id}
                className="flex items-center justify-between rounded border bg-card px-2 py-1.5 text-xs"
              >
                <div className="flex items-center gap-2">
                  {m.is_default ? (
                    <Star className="h-3 w-3 fill-amber-400 text-amber-500" />
                  ) : (
                    <span className="w-3" />
                  )}
                  <div>
                    <span className="font-medium">
                      {item?.name ?? m.service_catalog_item_id}
                    </span>
                    {item?.category_name && (
                      <span className="ml-1 text-muted-foreground">
                        ({item.category_name})
                      </span>
                    )}
                    <span className="ml-2 text-muted-foreground">
                      prio={m.priority_order}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {!m.is_default && (
                    <button
                      type="button"
                      onClick={() => handleSetDefault(m)}
                      title="Marcar como default"
                      disabled={setDefault.isPending}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-amber-600 disabled:opacity-40"
                    >
                      <Star className="h-3 w-3" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => handleRemove(m)}
                    title="Eliminar"
                    disabled={remove.isPending}
                    className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive disabled:opacity-40"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
