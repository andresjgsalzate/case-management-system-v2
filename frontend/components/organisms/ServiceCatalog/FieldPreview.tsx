"use client";

import type { ServiceCatalogField } from "@/lib/types";

interface Props {
  field: ServiceCatalogField;
  value?: string | null;
  onChange?: (value: string) => void;
  disabled?: boolean;
}

/**
 * Renderiza un campo del catálogo según su field_type.
 * Reusable en preview del builder y en el formulario de creación de caso.
 *
 * El value siempre es string (o null). Para checkbox: "true"/"false".
 * Para multiselect: JSON array stringified.
 */
export function FieldPreview({ field, value, onChange, disabled }: Props) {
  const id = `fld-${field.id}`;

  const labelEl = (
    <label htmlFor={id} className="text-sm font-medium text-foreground flex items-center gap-1">
      {field.label}
      {field.is_required && <span className="text-destructive">*</span>}
    </label>
  );

  const helpEl = field.help_text ? (
    <p className="text-xs text-muted-foreground">{field.help_text}</p>
  ) : null;

  const baseInputClass =
    "w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

  const placeholder = field.placeholder ?? undefined;

  function emit(v: string) {
    onChange?.(v);
  }

  switch (field.field_type) {
    case "text":
    case "email":
    case "phone":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <input
            id={id}
            type={field.field_type === "email" ? "email" : field.field_type === "phone" ? "tel" : "text"}
            value={value ?? ""}
            onChange={(e) => emit(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            className={baseInputClass}
          />
          {helpEl}
        </div>
      );

    case "textarea":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <textarea
            id={id}
            rows={3}
            value={value ?? ""}
            onChange={(e) => emit(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {helpEl}
        </div>
      );

    case "number":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <input
            id={id}
            type="number"
            value={value ?? ""}
            onChange={(e) => emit(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            min={(field.validation?.min as number) ?? undefined}
            max={(field.validation?.max as number) ?? undefined}
            className={baseInputClass}
          />
          {helpEl}
        </div>
      );

    case "date":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <input
            id={id}
            type="date"
            value={value ?? ""}
            onChange={(e) => emit(e.target.value)}
            disabled={disabled}
            className={baseInputClass}
          />
          {helpEl}
        </div>
      );

    case "datetime":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <input
            id={id}
            type="datetime-local"
            value={value ?? ""}
            onChange={(e) => emit(e.target.value)}
            disabled={disabled}
            className={baseInputClass}
          />
          {helpEl}
        </div>
      );

    case "select":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <select
            id={id}
            value={value ?? ""}
            onChange={(e) => emit(e.target.value)}
            disabled={disabled}
            className={baseInputClass}
          >
            <option value="">{placeholder ?? "Selecciona…"}</option>
            {(field.options ?? []).map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {helpEl}
        </div>
      );

    case "radio":
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <div className="flex flex-col gap-1.5">
            {(field.options ?? []).map((o) => (
              <label key={o.value} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name={id}
                  value={o.value}
                  checked={value === o.value}
                  onChange={() => emit(o.value)}
                  disabled={disabled}
                />
                <span>{o.label}</span>
              </label>
            ))}
          </div>
          {helpEl}
        </div>
      );

    case "checkbox": {
      const checked = value === "true" || value === "1";
      return (
        <div className="flex flex-col gap-1.5">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => emit(e.target.checked ? "true" : "false")}
              disabled={disabled}
              className="rounded"
            />
            <span className="font-medium text-foreground">
              {field.label} {field.is_required && <span className="text-destructive">*</span>}
            </span>
          </label>
          {helpEl}
        </div>
      );
    }

    case "multiselect": {
      const selected: string[] = (() => {
        if (!value) return [];
        try {
          return JSON.parse(value);
        } catch {
          return value.split(",");
        }
      })();
      return (
        <div className="flex flex-col gap-1.5">
          {labelEl}
          <div className="flex flex-col gap-1.5 rounded-md border border-input bg-background p-2">
            {(field.options ?? []).map((o) => {
              const isOn = selected.includes(o.value);
              return (
                <label key={o.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={isOn}
                    onChange={() => {
                      const next = isOn
                        ? selected.filter((s) => s !== o.value)
                        : [...selected, o.value];
                      emit(JSON.stringify(next));
                    }}
                    disabled={disabled}
                    className="rounded"
                  />
                  <span>{o.label}</span>
                </label>
              );
            })}
          </div>
          {helpEl}
        </div>
      );
    }

    default:
      return null;
  }
}
