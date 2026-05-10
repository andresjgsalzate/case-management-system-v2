"use client";

import { useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Plus, Pencil, Trash2, GripVertical, Eye, EyeOff } from "lucide-react";
import { Spinner } from "@/components/atoms/Spinner";
import { Button } from "@/components/atoms/Button";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import {
  useItemFields,
  useDeleteField,
  useReorderFields,
} from "@/hooks/useServiceCatalog";
import type { ServiceCatalogField, ServiceFieldType } from "@/lib/types";
import { FieldEditor } from "./FieldEditor";
import { FieldPreview } from "./FieldPreview";

const FIELD_TYPE_LABELS: Record<ServiceFieldType, string> = {
  text: "Texto corto",
  textarea: "Texto largo",
  number: "Número",
  date: "Fecha",
  datetime: "Fecha y hora",
  select: "Lista desplegable",
  radio: "Opciones (radio)",
  checkbox: "Casilla",
  multiselect: "Múltiple selección",
  email: "Email",
  phone: "Teléfono",
};

const PALETTE: { type: ServiceFieldType; label: string }[] = [
  { type: "text",        label: "Texto" },
  { type: "textarea",    label: "Párrafo" },
  { type: "number",      label: "Número" },
  { type: "date",        label: "Fecha" },
  { type: "select",      label: "Desplegable" },
  { type: "radio",       label: "Radio" },
  { type: "checkbox",    label: "Casilla" },
  { type: "multiselect", label: "Múltiple" },
  { type: "email",       label: "Email" },
  { type: "phone",       label: "Teléfono" },
];

interface Props {
  itemId: string;
}

export function FormBuilder({ itemId }: Props) {
  const confirm = useConfirm();
  const { data: fields = [], isLoading } = useItemFields(itemId);
  const del = useDeleteField();
  const reorder = useReorderFields();

  const [editorOpen, setEditorOpen] = useState<{ field?: ServiceCatalogField; presetType?: ServiceFieldType } | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = fields.findIndex((f) => f.id === active.id);
    const newIndex = fields.findIndex((f) => f.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(fields, oldIndex, newIndex);
    await reorder.mutateAsync({
      itemId,
      orderedIds: reordered.map((f) => f.id),
    });
  }

  async function handleDelete(field: ServiceCatalogField) {
    const ok = await confirm({
      title: `¿Eliminar campo "${field.label}"?`,
      description: "Si hay casos con valores en este campo, esos valores también se eliminarán.",
    });
    if (!ok) return;
    await del.mutateAsync(field.id);
  }

  return (
    <div className="rounded-lg border border-border bg-card flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Campos del formulario</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Arrastra para reordenar. Los cambios se guardan automáticamente.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted transition-colors"
          >
            {showPreview ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            {showPreview ? "Ocultar" : "Vista previa"}
          </button>
          <Button size="sm" onClick={() => setEditorOpen({})}>
            <Plus className="h-4 w-4" />
            Añadir campo
          </Button>
        </div>
      </div>

      {/* Palette (atajos) */}
      <div className="border-b border-border bg-muted/20 px-5 py-2 flex items-center gap-1.5 flex-wrap">
        <span className="text-[11px] text-muted-foreground mr-1">Crear rápido:</span>
        {PALETTE.map((p) => (
          <button
            key={p.type}
            type="button"
            onClick={() => setEditorOpen({ presetType: p.type })}
            className="text-[11px] rounded-md border border-border bg-card px-2 py-1 hover:border-primary/40 hover:bg-muted transition-colors"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className={showPreview ? "grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-border" : ""}>
        {/* Editor (siempre visible) */}
        <div className="flex flex-col">
          {isLoading ? (
            <div className="flex justify-center py-10"><Spinner /></div>
          ) : fields.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-muted-foreground">
              Aún no hay campos. Usa la barra de arriba o &ldquo;Añadir campo&rdquo;.
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={fields.map((f) => f.id)}
                strategy={verticalListSortingStrategy}
              >
                <ul className="divide-y divide-border">
                  {fields.map((f) => (
                    <SortableFieldRow
                      key={f.id}
                      field={f}
                      onEdit={() => setEditorOpen({ field: f })}
                      onDelete={() => handleDelete(f)}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          )}
        </div>

        {/* Preview */}
        {showPreview && (
          <div className="px-5 py-5 bg-muted/10">
            <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">
              Vista previa del formulario
            </p>
            {fields.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">Aún no hay campos.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {fields.map((f) => (
                  <FieldPreview key={f.id} field={f} disabled />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {editorOpen && (
        <FieldEditor
          itemId={itemId}
          field={editorOpen.field}
          presetType={editorOpen.presetType}
          existingFields={fields}
          onClose={() => setEditorOpen(null)}
        />
      )}
    </div>
  );
}

// ── Sortable row ──────────────────────────────────────────────────────────────

function SortableFieldRow({
  field,
  onEdit,
  onDelete,
}: {
  field: ServiceCatalogField;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: field.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 px-5 py-3 hover:bg-muted/40 transition-colors bg-card"
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground shrink-0"
        aria-label="Reordenar"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">{field.label}</span>
          {field.is_required && (
            <span className="text-[10px] uppercase rounded px-1.5 py-0.5 bg-destructive/10 text-destructive">
              Obligatorio
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground truncate">
          <span className="font-mono">{field.field_key}</span> · {FIELD_TYPE_LABELS[field.field_type]}
          {field.help_text && <span> · {field.help_text}</span>}
        </p>
      </div>
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
    </li>
  );
}
