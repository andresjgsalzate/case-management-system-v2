"use client";

import { Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { TaxonomyDetailPanel } from "@/components/organisms/TaxonomyDetailPanel";
import { TaxonomyEditModal } from "@/components/organisms/TaxonomyEditModal";
import { TaxonomyTreeView } from "@/components/organisms/TaxonomyTreeView";
import { useSecurityTaxonomies } from "@/hooks/useSecurityTaxonomies";
import type {
  SecurityTaxonomy,
  SecurityTaxonomyTreeNode,
} from "@/lib/types";

export default function TaxonomiesSettingsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<SecurityTaxonomy | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  // Flat list is used for drift detection (taxonomyMap) and parent picker.
  // TreeView consumes its own tree query internally.
  const { data: flatList } = useSecurityTaxonomies();

  const taxonomyMap = useMemo(() => {
    const m = new Map<string, SecurityTaxonomy>();
    for (const t of flatList ?? []) m.set(t.id, t);
    return m;
  }, [flatList]);

  // Only root taxonomies (those without a parent) can themselves
  // *be* a parent. This caps the hierarchy at depth 2 -- a child
  // taxonomy can never grow grandchildren. The backend still owns
  // the invariant; this just removes the foot-gun from the picker.
  const parentOptions = useMemo(() => {
    return (flatList ?? [])
      .filter((t) => t.parent_id === null)
      .map((t) => ({
        id: t.id, tuic_code: t.tuic_code, name: t.name,
        description: t.description ?? null,
      }));
  }, [flatList]);

  function handleSelect(node: SecurityTaxonomyTreeNode) {
    setSelectedId(node.id);
  }

  function openEdit(taxonomy: SecurityTaxonomy) {
    setEditing(taxonomy);
  }

  return (
    <div className="grid h-[calc(100vh-4rem)] grid-cols-1 gap-4 p-4 md:grid-cols-[320px_1fr]">
      <aside className="flex flex-col overflow-hidden rounded border bg-card">
        <header className="flex items-center justify-between border-b px-3 py-2">
          <h1 className="text-sm font-semibold">Taxonomías</h1>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-3.5 w-3.5" /> Nueva
          </button>
        </header>
        <div className="flex-1 overflow-hidden">
          <TaxonomyTreeView
            selectedId={selectedId}
            onSelect={handleSelect}
          />
        </div>
      </aside>

      <main className="overflow-hidden rounded border bg-card">
        <TaxonomyDetailPanel
          taxonomyId={selectedId}
          taxonomyMap={taxonomyMap}
          onEdit={openEdit}
          onDeleted={() => setSelectedId(null)}
        />
      </main>

      <TaxonomyEditModal
        isOpen={createOpen}
        existing={null}
        parentOptions={parentOptions}
        onClose={() => setCreateOpen(false)}
        onSaved={(created) => {
          setSelectedId(created.id);
        }}
      />

      <TaxonomyEditModal
        isOpen={editing !== null}
        existing={editing}
        parentOptions={parentOptions.filter((p) => p.id !== editing?.id)}
        onClose={() => setEditing(null)}
      />
    </div>
  );
}
