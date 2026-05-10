"use client";

import { useState } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import {
  useCreateField,
  useUpdateField,
} from "@/hooks/useServiceCatalog";
import type { ServiceCatalogField, ServiceFieldOption, ServiceFieldType } from "@/lib/types";
import { slugify, extractApiError } from "@/lib/utils";

const FIELD_TYPES: { value: ServiceFieldType; label: string; needsOptions: boolean }[] = [
  { value: "text",        label: "Texto corto",         needsOptions: false },
  { value: "textarea",    label: "Texto largo",         needsOptions: false },
  { value: "number",      label: "Número",              needsOptions: false },
  { value: "date",        label: "Fecha",               needsOptions: false },
  { value: "datetime",    label: "Fecha y hora",        needsOptions: false },
  { value: "select",      label: "Lista desplegable",   needsOptions: true  },
  { value: "radio",       label: "Opciones (radio)",    needsOptions: true  },
  { value: "checkbox",    label: "Casilla (sí/no)",     needsOptions: false },
  { value: "multiselect", label: "Múltiple selección",  needsOptions: true  },
  { value: "email",       label: "Email",               needsOptions: false },
  { value: "phone",       label: "Teléfono",            needsOptions: false },
];

interface Props {
  itemId: string;
  field?: ServiceCatalogField;
  presetType?: ServiceFieldType;
  existingFields: ServiceCatalogField[];
  onClose: () => void;
}

export function FieldEditor({ itemId, field, presetType, existingFields, onClose }: Props) {
  const isEdit = !!field;

  const [label, setLabel] = useState(field?.label ?? "");
  const [fieldKey, setFieldKey] = useState(field?.field_key ?? "");
  const [fieldType, setFieldType] = useState<ServiceFieldType>(field?.field_type ?? presetType ?? "text");
  const [isRequired, setIsRequired] = useState(field?.is_required ?? false);
  const [placeholder, setPlaceholder] = useState(field?.placeholder ?? "");
  const [helpText, setHelpText] = useState(field?.help_text ?? "");
  const [options, setOptions] = useState<ServiceFieldOption[]>(field?.options ?? []);
  const [validation, setValidation] = useState<Record<string, unknown>>(field?.validation ?? {});
  const [error, setError] = useState<string | null>(null);

  const create = useCreateField();
  const update = useUpdateField();

  const typeMeta = FIELD_TYPES.find((t) => t.value === fieldType)!;

  function addOption() {
    setOptions((prev) => [...prev, { value: "", label: "" }]);
  }
  function updateOption(idx: number, key: keyof ServiceFieldOption, val: string) {
    setOptions((prev) => prev.map((o, i) => (i === idx ? { ...o, [key]: val } : o)));
  }
  /**
   * Cuando cambia el LABEL: auto-genera el value desde el label si el value
   * estaba vacío o seguía sincronizado con el label anterior. Si el admin ya
   * personalizó el value manualmente, respeta su edición.
   */
  function updateOptionLabel(idx: number, newLabel: string) {
    setOptions((prev) =>
      prev.map((o, i) => {
        if (i !== idx) return o;
        const wasAuto = !o.value || o.value === slugify(o.label).replace(/-/g, "_");
        return {
          label: newLabel,
          value: wasAuto ? slugify(newLabel).replace(/-/g, "_") : o.value,
        };
      })
    );
  }
  function removeOption(idx: number) {
    setOptions((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    // Validations
    const labelTrim = label.trim();
    const keyTrim = fieldKey.trim();
    if (!labelTrim) return setError("El label es obligatorio");
    if (!keyTrim) return setError("La clave (field_key) es obligatoria");
    if (!/^[a-z][a-z0-9_]*$/.test(keyTrim)) {
      return setError("La clave debe empezar con letra minúscula y solo contener letras, números y _");
    }
    if (typeMeta.needsOptions && options.length === 0) {
      return setError("Este tipo de campo requiere al menos una opción");
    }
    if (typeMeta.needsOptions) {
      const seenValues = new Set<string>();
      for (const o of options) {
        if (!o.value.trim() || !o.label.trim()) return setError("Las opciones no pueden tener value/label vacíos");
        if (seenValues.has(o.value)) return setError(`Hay valores de opción duplicados: "${o.value}"`);
        seenValues.add(o.value);
      }
    }

    // Check duplicate field_key in same item
    const dup = existingFields.find((f) => f.field_key === keyTrim && f.id !== field?.id);
    if (dup) return setError(`Ya existe un campo con la clave "${keyTrim}"`);

    try {
      const dto = {
        label: labelTrim,
        field_type: fieldType,
        is_required: isRequired,
        placeholder: placeholder || undefined,
        help_text: helpText || undefined,
        options: typeMeta.needsOptions ? options : undefined,
        validation: Object.keys(validation).length > 0 ? validation : undefined,
      };

      if (isEdit && field) {
        await update.mutateAsync({ id: field.id, dto });
      } else {
        await create.mutateAsync({
          item_id: itemId,
          field_key: keyTrim,
          ...dto,
          sort_order: existingFields.length,
        });
      }
      onClose();
    } catch (err: unknown) {
      setError(extractApiError(err, "Error al guardar el campo"));
    }
  }

  const busy = create.isPending || update.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <h2 className="text-sm font-semibold text-foreground">
            {isEdit ? "Editar campo" : "Nuevo campo"}
          </h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 flex flex-col gap-4 overflow-y-auto">
          <Field label="Etiqueta visible" required>
            <input
              type="text"
              value={label}
              onChange={(e) => {
                setLabel(e.target.value);
                if (!isEdit && !fieldKey) {
                  setFieldKey(slugify(e.target.value).replace(/-/g, "_"));
                }
              }}
              required
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              placeholder="ej: ¿Qué aplicación reporta?"
            />
          </Field>

          <Field label="Clave técnica (interna)" required>
            <input
              type="text"
              value={fieldKey}
              onChange={(e) => setFieldKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
              required
              disabled={isEdit}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm font-mono disabled:opacity-50"
              placeholder="aplicacion_afectada"
            />
            <p className="text-xs text-muted-foreground mt-1">
              No se puede cambiar después de crear el campo. Solo letras minúsculas, números y _.
            </p>
          </Field>

          <Field label="Tipo de campo" required>
            <select
              value={fieldType}
              onChange={(e) => setFieldType(e.target.value as ServiceFieldType)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              disabled={isEdit}
            >
              {FIELD_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            {isEdit && (
              <p className="text-xs text-muted-foreground mt-1">
                El tipo no se puede cambiar después de crear el campo.
              </p>
            )}
          </Field>

          {/* Opciones — solo para select/radio/multiselect */}
          {typeMeta.needsOptions && (
            <Field label="Opciones" required>
              <div className="flex flex-col gap-2">
                <p className="text-xs text-muted-foreground">
                  La <strong>etiqueta visible</strong> es lo que ve el usuario
                  (puede tener mayúsculas, acentos, símbolos). El <strong>valor interno</strong>
                  {" "}se guarda en la base de datos y debe ser estable — se autogenera al
                  escribir la etiqueta, pero puedes personalizarlo si lo necesitas.
                </p>

                {/* Headers */}
                {options.length > 0 && (
                  <div className="flex gap-2 px-1">
                    <span className="flex-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                      Etiqueta visible
                    </span>
                    <span className="flex-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                      Valor interno (auto)
                    </span>
                    <span className="w-7" />
                  </div>
                )}

                {options.map((opt, idx) => (
                  <div key={idx} className="flex gap-2">
                    <input
                      type="text"
                      value={opt.label}
                      onChange={(e) => updateOptionLabel(idx, e.target.value)}
                      placeholder="ej: Bogotá"
                      className="flex-1 h-8 rounded-md border border-input bg-background px-2 text-xs"
                    />
                    <input
                      type="text"
                      value={opt.value}
                      onChange={(e) => updateOption(idx, "value", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                      placeholder="bogota"
                      title="Valor interno — solo minúsculas, números y _"
                      className="flex-1 h-8 rounded-md border border-input bg-muted/40 px-2 text-xs font-mono text-muted-foreground"
                    />
                    <button
                      type="button"
                      onClick={() => removeOption(idx)}
                      className="p-1.5 rounded text-muted-foreground hover:text-destructive"
                      title="Eliminar opción"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addOption}
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline self-start"
                >
                  <Plus className="h-3 w-3" />
                  Añadir opción
                </button>
              </div>
            </Field>
          )}

          <div className="grid grid-cols-2 gap-3">
            <Field label="Placeholder (opcional)">
              <input
                type="text"
                value={placeholder}
                onChange={(e) => setPlaceholder(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              />
            </Field>
            <label className="flex items-end gap-2 pb-2">
              <input
                type="checkbox"
                checked={isRequired}
                onChange={(e) => setIsRequired(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-foreground">Campo obligatorio</span>
            </label>
          </div>

          <Field label="Texto de ayuda (opcional)">
            <input
              type="text"
              value={helpText}
              onChange={(e) => setHelpText(e.target.value)}
              maxLength={500}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
              placeholder="Aparece debajo del campo para guiar al usuario"
            />
          </Field>

          {/* Validaciones según tipo */}
          {(fieldType === "text" || fieldType === "textarea") && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Longitud mínima">
                <input
                  type="number"
                  min={0}
                  value={(validation.min_length as number) ?? ""}
                  onChange={(e) =>
                    setValidation((v) => ({
                      ...v,
                      min_length: e.target.value ? parseInt(e.target.value) : undefined,
                    }))
                  }
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                />
              </Field>
              <Field label="Longitud máxima">
                <input
                  type="number"
                  min={0}
                  value={(validation.max_length as number) ?? ""}
                  onChange={(e) =>
                    setValidation((v) => ({
                      ...v,
                      max_length: e.target.value ? parseInt(e.target.value) : undefined,
                    }))
                  }
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                />
              </Field>
            </div>
          )}
          {fieldType === "number" && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Mínimo">
                <input
                  type="number"
                  value={(validation.min as number) ?? ""}
                  onChange={(e) =>
                    setValidation((v) => ({
                      ...v,
                      min: e.target.value ? parseFloat(e.target.value) : undefined,
                    }))
                  }
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                />
              </Field>
              <Field label="Máximo">
                <input
                  type="number"
                  value={(validation.max as number) ?? ""}
                  onChange={(e) =>
                    setValidation((v) => ({
                      ...v,
                      max: e.target.value ? parseFloat(e.target.value) : undefined,
                    }))
                  }
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                />
              </Field>
            </div>
          )}

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-border mt-2">
            <Button variant="outline" type="button" onClick={onClose} disabled={busy}>
              Cancelar
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear campo"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-foreground">
        {label} {required && <span className="text-destructive">*</span>}
      </label>
      {children}
    </div>
  );
}
