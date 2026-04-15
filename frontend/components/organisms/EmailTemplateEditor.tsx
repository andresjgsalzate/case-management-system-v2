// frontend/components/organisms/EmailTemplateEditor.tsx
"use client";

import { useState, useRef, useCallback } from "react";
import { Plus, Trash2, ChevronUp, ChevronDown, X, Save, Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/atoms/Spinner";
import {
  BLOCK_TYPES, SCOPE_OPTIONS, SCOPE_VARIABLES,
  defaultProps, renderEmailPreview,
} from "@/lib/emailRenderer";
import {
  useCreateEmailTemplate, useUpdateEmailTemplate,
  type Block, type BlockType, type EmailTemplate,
} from "@/hooks/useEmailConfig";

interface Props {
  template?: EmailTemplate;
  onClose: () => void;
}

// ── Variable insert bar ───────────────────────────────────────────────────────

function VariableBar({
  scope,
  onInsert,
}: {
  scope: string;
  onInsert: (variable: string) => void;
}) {
  const vars = SCOPE_VARIABLES[scope] ?? SCOPE_VARIABLES.global;
  if (!vars.length) return null;
  return (
    <div className="flex flex-wrap gap-1 mb-2">
      {vars.map((v) => (
        <button
          key={v.name}
          type="button"
          onClick={() => onInsert(v.name)}
          title={v.description}
          className="font-mono text-[11px] px-2 py-0.5 rounded bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20 transition-colors"
        >
          {`{${v.name}}`}
        </button>
      ))}
    </div>
  );
}

// ── Field with variable insertion ─────────────────────────────────────────────

function TextField({
  label,
  value,
  onChange,
  scope,
  multiline = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  scope: string;
  multiline?: boolean;
  placeholder?: string;
}) {
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null);

  function insertVar(name: string) {
    const ph = `{${name}}`;
    const el = ref.current;
    if (!el) { onChange(value + ph); return; }
    const s = el.selectionStart ?? value.length;
    const e = el.selectionEnd ?? value.length;
    const next = value.slice(0, s) + ph + value.slice(e);
    onChange(next);
    setTimeout(() => { el.focus(); el.setSelectionRange(s + ph.length, s + ph.length); }, 0);
  }

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <VariableBar scope={scope} onInsert={insertVar} />
      {multiline ? (
        <textarea
          ref={ref as React.RefObject<HTMLTextAreaElement>}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={3}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      ) : (
        <input
          ref={ref as React.RefObject<HTMLInputElement>}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      )}
    </div>
  );
}

// ── Block props editor ────────────────────────────────────────────────────────

function BlockPropsEditor({
  block,
  scope,
  onChange,
}: {
  block: Block;
  scope: string;
  onChange: (props: Record<string, unknown>) => void;
}) {
  const p = block.props as Record<string, string>;
  const set = (key: string, val: unknown) => onChange({ ...block.props, [key]: val });

  const colorField = (label: string, key: string) => (
    <div className="flex items-center gap-2">
      <label className="text-xs text-muted-foreground w-28 shrink-0">{label}</label>
      <input
        type="color"
        value={(p[key] as string) || "#000000"}
        onChange={(e) => set(key, e.target.value)}
        className="h-7 w-12 rounded border border-border cursor-pointer"
      />
      <input
        type="text"
        value={(p[key] as string) || ""}
        onChange={(e) => set(key, e.target.value)}
        className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary/30"
      />
    </div>
  );

  switch (block.type) {
    case "header":
      return (
        <div className="flex flex-col gap-3 pt-2">
          <TextField label="Título" value={p.title||""} onChange={v=>set("title",v)} scope={scope} placeholder="Título del encabezado" />
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">URL del logo</label>
            <input type="text" value={p.logo_url||""} onChange={e=>set("logo_url",e.target.value)} placeholder="https://…" className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          {colorField("Color de fondo", "bg_color")}
        </div>
      );

    case "hero":
      return (
        <div className="flex flex-col gap-3 pt-2">
          <TextField label="Título" value={p.title||""} onChange={v=>set("title",v)} scope={scope} placeholder="Título grande" />
          <TextField label="Subtítulo" value={p.subtitle||""} onChange={v=>set("subtitle",v)} scope={scope} placeholder="Subtítulo opcional" />
          {colorField("Color de fondo", "bg_color")}
          {colorField("Color de texto", "text_color")}
        </div>
      );

    case "body":
    case "text":
      return (
        <div className="pt-2">
          <TextField label="Contenido" value={p.content||""} onChange={v=>set("content",v)} scope={scope} multiline placeholder="Escribe el contenido…" />
        </div>
      );

    case "button":
      return (
        <div className="flex flex-col gap-3 pt-2">
          <TextField label="Etiqueta" value={p.label||""} onChange={v=>set("label",v)} scope={scope} placeholder="Ver caso" />
          <TextField label="URL" value={p.url||""} onChange={v=>set("url",v)} scope={scope} placeholder="https://… o {variable}" />
          {colorField("Color de fondo", "bg_color")}
          {colorField("Color de texto", "text_color")}
        </div>
      );

    case "divider":
      return (
        <div className="flex flex-col gap-3 pt-2">
          {colorField("Color", "color")}
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground w-28 shrink-0">Grosor (px)</label>
            <input type="number" min={1} max={8} value={p.thickness||"1"} onChange={e=>set("thickness",Number(e.target.value))} className="w-20 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
          </div>
        </div>
      );

    case "footer":
      return (
        <div className="flex flex-col gap-3 pt-2">
          <TextField label="Contenido" value={p.content||""} onChange={v=>set("content",v)} scope={scope} multiline placeholder="© 2026 Mi empresa" />
          {colorField("Color de fondo", "bg_color")}
          {colorField("Color de texto", "text_color")}
        </div>
      );

    case "data_table": {
      const rows = (block.props.rows as { label: string; value: string }[]) || [];
      return (
        <div className="flex flex-col gap-2 pt-2">
          <label className="text-xs font-medium text-muted-foreground">Filas</label>
          {rows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <input type="text" value={row.label} onChange={e => { const r=[...rows]; r[i]={...r[i],label:e.target.value}; set("rows",r); }} placeholder="Etiqueta" className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
              <input type="text" value={row.value} onChange={e => { const r=[...rows]; r[i]={...r[i],value:e.target.value}; set("rows",r); }} placeholder="Valor o {variable}" className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
              <button type="button" onClick={() => set("rows", rows.filter((_,j)=>j!==i))} className="text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          ))}
          <button type="button" onClick={() => set("rows", [...rows, { label: "", value: "" }])} className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
            <Plus className="h-3.5 w-3.5" /> Añadir fila
          </button>
          <VariableBar scope={scope} onInsert={v => { const r=[...rows,{label:"",value:`{${v}}`}]; set("rows",r); }} />
        </div>
      );
    }

    case "alert":
      return (
        <div className="flex flex-col gap-3 pt-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Tipo</label>
            <select value={p.alert_type||"info"} onChange={e=>set("alert_type",e.target.value)} className="rounded-md border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30">
              {["info","warning","error","success"].map(t=><option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <TextField label="Mensaje" value={p.message||""} onChange={v=>set("message",v)} scope={scope} multiline placeholder="Mensaje de la alerta" />
        </div>
      );

    case "image":
      return (
        <div className="flex flex-col gap-3 pt-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">URL de imagen</label>
            <input type="text" value={p.url||""} onChange={e=>set("url",e.target.value)} placeholder="https://…" className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Texto alternativo</label>
            <input type="text" value={p.alt||""} onChange={e=>set("alt",e.target.value)} className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Ancho</label>
            <input type="text" value={p.width||"100%"} onChange={e=>set("width",e.target.value)} placeholder="100% o 400px" className="w-32 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
        </div>
      );

    default:
      return <p className="text-xs text-muted-foreground pt-2 italic">Sin propiedades editables.</p>;
  }
}

// ── Main editor ───────────────────────────────────────────────────────────────

export function EmailTemplateEditor({ template, onClose }: Props) {
  const [name, setName] = useState(template?.name ?? "Nueva plantilla");
  const [scope, setScope] = useState(template?.scope ?? "global");
  const [isActive, setIsActive] = useState(template?.is_active ?? false);
  const [blocks, setBlocks] = useState<Block[]>(template?.blocks ?? []);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [showPreview, setShowPreview] = useState(true);

  const createTpl = useCreateEmailTemplate();
  const updateTpl = useUpdateEmailTemplate();
  const isPending = createTpl.isPending || updateTpl.isPending;

  const addBlock = useCallback((type: BlockType) => {
    setBlocks(prev => [...prev, { type, props: defaultProps(type) }]);
    setSelectedIdx(prev => (prev === null ? 0 : blocks.length));
  }, [blocks.length]);

  const removeBlock = (idx: number) => {
    setBlocks(prev => prev.filter((_, i) => i !== idx));
    setSelectedIdx(null);
  };

  const moveBlock = (idx: number, dir: "up" | "down") => {
    setBlocks(prev => {
      const next = [...prev];
      const target = dir === "up" ? idx - 1 : idx + 1;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
    setSelectedIdx(dir === "up" ? idx - 1 : idx + 1);
  };

  const updateProps = (idx: number, props: Record<string, unknown>) => {
    setBlocks(prev => prev.map((b, i) => i === idx ? { ...b, props } : b));
  };

  async function handleSave() {
    if (template) {
      await updateTpl.mutateAsync({ id: template.id, name, scope, blocks, is_active: isActive });
    } else {
      await createTpl.mutateAsync({ name, scope, blocks });
    }
    onClose();
  }

  const previewHtml = renderEmailPreview(blocks, {});

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-border bg-card shrink-0">
        <div className="flex-1 flex items-center gap-3 min-w-0">
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/30 w-48"
          />
          <select
            value={scope}
            onChange={e => setScope(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
          >
            {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
            <button
              type="button"
              role="switch"
              aria-checked={isActive}
              onClick={() => setIsActive(v => !v)}
              className={cn(
                "relative inline-flex h-5 w-9 rounded-full border-2 border-transparent transition-colors",
                isActive ? "bg-primary" : "bg-muted-foreground/30"
              )}
            >
              <span className={cn("inline-block h-4 w-4 rounded-full bg-white shadow transition-all", isActive ? "translate-x-4" : "translate-x-0")} />
            </button>
            Activa
          </label>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowPreview(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-border hover:bg-muted text-muted-foreground transition-colors"
          >
            {showPreview ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            {showPreview ? "Ocultar preview" : "Ver preview"}
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {isPending ? <Spinner size="sm" /> : <Save className="h-3.5 w-3.5" />}
            Guardar
          </button>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground p-1.5 rounded-md hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className={cn("flex-1 overflow-hidden grid", showPreview ? "grid-cols-[200px_1fr_1fr]" : "grid-cols-[200px_1fr]")}>
        {/* Block palette */}
        <div className="border-r border-border overflow-y-auto p-3 flex flex-col gap-1">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Bloques</p>
          {BLOCK_TYPES.map(bt => (
            <button
              key={bt.type}
              type="button"
              onClick={() => addBlock(bt.type)}
              title={bt.description}
              className="flex items-center gap-2 px-2 py-2 rounded-md text-sm text-left hover:bg-muted transition-colors"
            >
              <Plus className="h-3 w-3 shrink-0 text-primary" />
              <span className="truncate">{bt.label}</span>
            </button>
          ))}
        </div>

        {/* Canvas */}
        <div className="overflow-y-auto p-4 flex flex-col gap-2 border-r border-border">
          {blocks.length === 0 && (
            <div className="flex flex-col items-center justify-center h-40 text-muted-foreground text-sm italic">
              Haz clic en un bloque para añadirlo
            </div>
          )}
          {blocks.map((block, idx) => {
            const isSelected = selectedIdx === idx;
            const btMeta = BLOCK_TYPES.find(b => b.type === block.type);
            return (
              <div
                key={idx}
                className={cn(
                  "rounded-md border transition-colors",
                  isSelected ? "border-primary/50 bg-primary/5" : "border-border hover:border-primary/30"
                )}
              >
                {/* Block header row */}
                <div
                  className="flex items-center gap-2 px-3 py-2 cursor-pointer"
                  onClick={() => setSelectedIdx(isSelected ? null : idx)}
                >
                  <span className="flex-1 text-sm font-medium truncate">{btMeta?.label ?? block.type}</span>
                  <div className="flex items-center gap-1 shrink-0">
                    <button type="button" onClick={e => { e.stopPropagation(); moveBlock(idx, "up"); }} disabled={idx === 0} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
                    <button type="button" onClick={e => { e.stopPropagation(); moveBlock(idx, "down"); }} disabled={idx === blocks.length - 1} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronDown className="h-3.5 w-3.5" /></button>
                    <button type="button" onClick={e => { e.stopPropagation(); removeBlock(idx); }} className="p-0.5 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
                {/* Inline props editor */}
                {isSelected && (
                  <div className="border-t border-border px-3 pb-3">
                    <BlockPropsEditor
                      block={block}
                      scope={scope}
                      onChange={props => updateProps(idx, props)}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Preview iframe */}
        {showPreview && (
          <div className="overflow-hidden flex flex-col">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-4 pt-3 pb-1">Vista previa</p>
            <iframe
              srcDoc={previewHtml}
              className="flex-1 w-full border-0"
              title="Email preview"
              sandbox="allow-same-origin"
            />
          </div>
        )}
      </div>
    </div>
  );
}
