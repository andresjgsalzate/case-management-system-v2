"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { ApiResponse } from "@/lib/types";
import {
  Bell, ChevronDown, ChevronUp, RotateCcw, Save, Plus, X,
  UserCheck, Clock, BookOpen, Zap, Info, AlertTriangle, Send,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/atoms/Spinner";

// ── Types ──────────────────────────────────────────────────────────────────────

interface NotifTemplate {
  id: string;
  event_name: string;
  notification_type: string;
  title: string;
  body: string;
  is_enabled: boolean;
  variables: string[];
  updated_at: string;
}

interface User {
  id: string;
  full_name: string;
  email: string;
  role?: string;
}

// ── Config ─────────────────────────────────────────────────────────────────────

const EVENT_META: Record<string, { label: string; description: string; icon: React.ElementType; color: string }> = {
  "case.assigned":       { label: "Caso asignado",         description: "Cuando se asigna un caso a un agente",             icon: UserCheck, color: "text-blue-500"    },
  "case.status_changed": { label: "Cambio de estado",       description: "Cuando un caso cambia de estado",                  icon: Info,      color: "text-violet-500"  },
  "case.updated":        { label: "Caso actualizado",       description: "Cuando se edita un caso asignado",                 icon: Info,      color: "text-slate-500"   },
  "sla.breached":        { label: "SLA vencido",            description: "Cuando un caso supera el tiempo límite de SLA",    icon: Clock,     color: "text-red-500"     },
  "kb.review_requested": { label: "Revisión KB",            description: "Cuando un artículo de KB entra en revisión",       icon: BookOpen,  color: "text-emerald-500" },
  "mention":             { label: "Mención",                description: "Cuando alguien menciona a un usuario en una nota", icon: Zap,       color: "text-yellow-500"  },
};

const NOTIF_TYPES = [
  { value: "info",              label: "Info",             icon: Info      },
  { value: "case_assigned",     label: "Caso asignado",    icon: UserCheck },
  { value: "case_updated",      label: "Caso actualizado", icon: Info      },
  { value: "sla_breach",        label: "SLA vencido",      icon: Clock     },
  { value: "kb_review_request", label: "Revisión KB",      icon: BookOpen  },
  { value: "mention",           label: "Mención",          icon: Zap       },
];

// Variables that can be used in manual notifications and get resolved per user
const MANUAL_VARIABLES = [
  { name: "full_name", description: "Nombre completo del destinatario" },
  { name: "email",     description: "Email del destinatario"           },
];

// ── Hooks ──────────────────────────────────────────────────────────────────────

function useTemplates() {
  return useQuery<NotifTemplate[]>({
    queryKey: ["notification-templates"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<NotifTemplate[]>>("/notifications/templates");
      return data.data ?? [];
    },
  });
}

function useUsers() {
  return useQuery<User[]>({
    queryKey: ["users-list"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<{ users: User[] }>>("/users?limit=200");
      return (data.data as any)?.users ?? data.data ?? [];
    },
  });
}

function useUpdateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<NotifTemplate> & { id: string }) =>
      apiClient.patch(`/notifications/templates/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-templates"] }),
  });
}

function useResetTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.post(`/notifications/templates/${id}/reset`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-templates"] }),
  });
}

function useCreateManual() {
  return useMutation({
    mutationFn: (body: {
      user_ids: string[];
      title: string;
      body: string;
      notification_type: string;
    }) => apiClient.post("/notifications/manual", body),
  });
}

// ── Template row ───────────────────────────────────────────────────────────────

function TemplateRow({ template }: { template: NotifTemplate }) {
  const [expanded, setExpanded] = useState(false);
  const [title, setTitle] = useState(template.title);
  const [body, setBody] = useState(template.body);
  const [dirty, setDirty] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const bodyRef  = useRef<HTMLTextAreaElement>(null);

  const update = useUpdateTemplate();
  const reset  = useResetTemplate();
  const meta   = EVENT_META[template.event_name];
  const Icon   = meta?.icon ?? Bell;

  function insertVar(variable: string, target: "title" | "body") {
    const ph = `{${variable}}`;
    if (target === "title" && titleRef.current) {
      const el = titleRef.current;
      const s = el.selectionStart ?? title.length;
      const e = el.selectionEnd ?? title.length;
      const next = title.slice(0, s) + ph + title.slice(e);
      setTitle(next); setDirty(true);
      setTimeout(() => { el.focus(); el.setSelectionRange(s + ph.length, s + ph.length); }, 0);
    } else if (target === "body" && bodyRef.current) {
      const el = bodyRef.current;
      const s = el.selectionStart ?? body.length;
      const e = el.selectionEnd ?? body.length;
      const next = body.slice(0, s) + ph + body.slice(e);
      setBody(next); setDirty(true);
      setTimeout(() => { el.focus(); el.setSelectionRange(s + ph.length, s + ph.length); }, 0);
    }
  }

  async function handleSave() {
    await update.mutateAsync({ id: template.id, title, body });
    setDirty(false);
  }

  return (
    <div className={cn("border-b border-border last:border-0", !template.is_enabled && "opacity-60")}>
      <div className="flex items-center gap-3 px-4 py-3">
        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted", meta?.color)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground">{meta?.label ?? template.event_name}</p>
          <p className="text-xs text-muted-foreground truncate">{meta?.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => update.mutateAsync({ id: template.id, is_enabled: !template.is_enabled })}
            className={cn(
              "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
              template.is_enabled ? "bg-primary" : "bg-muted-foreground/30"
            )}
            role="switch" aria-checked={template.is_enabled}
          >
            <span className={cn(
              "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-all",
              template.is_enabled ? "translate-x-4" : "translate-x-0"
            )} />
          </button>
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted transition-colors"
          >
            Editar {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 flex flex-col gap-3 bg-muted/20 border-t border-border">
          {template.variables.length > 0 && (
            <div className="pt-3">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                Variables disponibles — clic para insertar
              </p>
              <div className="flex flex-wrap gap-1.5">
                {template.variables.map((v) => (
                  <div key={v} className="flex rounded-md overflow-hidden border border-border text-[11px]">
                    <button type="button" onClick={() => insertVar(v, "title")}
                      className="font-mono px-2 py-1 bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                      title="Insertar en título">
                      {`{${v}}`}
                    </button>
                    <button type="button" onClick={() => insertVar(v, "body")}
                      className="px-2 py-1 bg-muted text-muted-foreground hover:bg-muted/80 border-l border-border transition-colors"
                      title="Insertar en mensaje">
                      msg
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-foreground">Título</label>
            <input ref={titleRef} type="text" value={title}
              onChange={(e) => { setTitle(e.target.value); setDirty(true); }}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-foreground">Mensaje</label>
            <textarea ref={bodyRef} value={body} rows={2}
              onChange={(e) => { setBody(e.target.value); setDirty(true); }}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>

          {/* Preview */}
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Vista previa</p>
            <p className="text-sm font-semibold text-foreground">{title || "—"}</p>
            <p className="text-xs text-muted-foreground">{body || "—"}</p>
          </div>

          <div className="flex items-center gap-2">
            <button type="button" onClick={handleSave} disabled={!dirty || update.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              <Save className="h-3.5 w-3.5" />
              {update.isPending ? "Guardando…" : "Guardar"}
            </button>
            <button type="button" onClick={() => reset.mutateAsync(template.id)} disabled={reset.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-border hover:bg-muted text-muted-foreground transition-colors">
              <RotateCcw className="h-3.5 w-3.5" />
              Restaurar
            </button>
            {!dirty && !update.isPending && (
              <span className="text-xs text-emerald-600">Guardado</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Create notification panel ──────────────────────────────────────────────────

function CreateNotificationPanel({ onClose }: { onClose: () => void }) {
  const [selectedUsers, setSelectedUsers] = useState<User[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [type, setType] = useState("info");
  const [userSearch, setUserSearch] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const bodyRef  = useRef<HTMLTextAreaElement>(null);

  const { data: users = [] } = useUsers();
  const create = useCreateManual();

  const filtered = users.filter(
    (u) =>
      !selectedUsers.find((s) => s.id === u.id) &&
      (u.full_name.toLowerCase().includes(userSearch.toLowerCase()) ||
       u.email.toLowerCase().includes(userSearch.toLowerCase()))
  );

  function insertVar(variable: string, target: "title" | "body") {
    const ph = `{${variable}}`;
    if (target === "title" && titleRef.current) {
      const el = titleRef.current;
      const s = el.selectionStart ?? title.length;
      const e = el.selectionEnd ?? title.length;
      setTitle(title.slice(0, s) + ph + title.slice(e));
      setTimeout(() => { el.focus(); el.setSelectionRange(s + ph.length, s + ph.length); }, 0);
    } else if (target === "body" && bodyRef.current) {
      const el = bodyRef.current;
      const s = el.selectionStart ?? body.length;
      const e = el.selectionEnd ?? body.length;
      setBody(body.slice(0, s) + ph + body.slice(e));
      setTimeout(() => { el.focus(); el.setSelectionRange(s + ph.length, s + ph.length); }, 0);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedUsers.length || !title.trim() || !body.trim()) return;
    await create.mutateAsync({
      user_ids: selectedUsers.map((u) => u.id),
      title: title.trim(),
      body: body.trim(),
      notification_type: type,
    });
    onClose();
  }

  const canSubmit = selectedUsers.length > 0 && title.trim() && body.trim() && !create.isPending;

  return (
    <div className="rounded-lg border border-border bg-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Plus className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">Nueva notificación</span>
        </div>
        <button type="button" onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">

        {/* Variables disponibles */}
        <div className="rounded-md border border-border bg-muted/30 p-3 flex flex-col gap-2">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Variables disponibles
          </p>
          <p className="text-[11px] text-muted-foreground">
            Se resuelven individualmente para cada destinatario.
          </p>
          <div className="flex flex-col gap-1.5">
            {MANUAL_VARIABLES.map((v) => (
              <div key={v.name} className="flex items-center justify-between gap-2">
                <div>
                  <code className="text-[11px] font-mono text-primary">{`{${v.name}}`}</code>
                  <span className="text-[11px] text-muted-foreground ml-2">{v.description}</span>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button type="button" onClick={() => insertVar(v.name, "title")}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors">
                    título
                  </button>
                  <button type="button" onClick={() => insertVar(v.name, "body")}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border hover:bg-muted/80 transition-colors">
                    msg
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recipients */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-foreground">Destinatarios *</label>
          <div className="relative">
            <input
              type="text"
              placeholder="Buscar usuario…"
              value={userSearch}
              onChange={(e) => { setUserSearch(e.target.value); setShowDropdown(true); }}
              onFocus={() => setShowDropdown(true)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            {showDropdown && userSearch && filtered.length > 0 && (
              <div className="absolute z-50 top-full mt-1 w-full rounded-md border border-border bg-card shadow-lg max-h-40 overflow-y-auto">
                {filtered.slice(0, 8).map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => {
                      setSelectedUsers((p) => [...p, u]);
                      setUserSearch("");
                      setShowDropdown(false);
                    }}
                    className="w-full flex flex-col px-3 py-2 hover:bg-muted text-left transition-colors"
                  >
                    <span className="text-sm font-medium text-foreground">{u.full_name}</span>
                    <span className="text-xs text-muted-foreground">{u.email}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {selectedUsers.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {selectedUsers.map((u) => (
                <span key={u.id}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                  {u.full_name}
                  <button type="button" onClick={() => setSelectedUsers((p) => p.filter((x) => x.id !== u.id))}>
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Type */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-foreground">Tipo</label>
          <select value={type} onChange={(e) => setType(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
            {NOTIF_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        {/* Title */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-foreground">Título *</label>
          <input ref={titleRef} type="text" value={title} placeholder="Ej. Actualización importante"
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>

        {/* Body */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-foreground">Mensaje *</label>
          <textarea ref={bodyRef} value={body} rows={4} placeholder="Hola {full_name}, …"
            onChange={(e) => setBody(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>

        {/* Preview */}
        {(title || body) && (
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">Vista previa</p>
            <p className="text-sm font-semibold text-foreground">{title || "—"}</p>
            <p className="text-xs text-muted-foreground">{body || "—"}</p>
          </div>
        )}

        <button type="submit" disabled={!canSubmit}
          className="flex items-center justify-center gap-2 w-full py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mt-auto">
          <Send className="h-4 w-4" />
          {create.isPending
            ? "Enviando…"
            : `Enviar a ${selectedUsers.length} usuario${selectedUsers.length !== 1 ? "s" : ""}`}
        </button>

        {create.isSuccess && (
          <p className="text-xs text-center text-emerald-600">Notificación enviada correctamente</p>
        )}
      </form>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function NotificationsSettingsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const { data: templates = [], isLoading } = useTemplates();

  return (
    <div className="flex flex-col gap-5 w-full">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Notificaciones</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configura los eventos que generan notificaciones y personaliza sus mensajes.
            Usa <code className="text-xs bg-muted px-1 py-0.5 rounded">{"{variable}"}</code> para datos dinámicos.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors shrink-0",
            showCreate
              ? "bg-muted text-foreground border border-border"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showCreate ? "Cancelar" : "Nueva notificación"}
        </button>
      </div>

      {/* Main layout — always grid so the card stretches to full width */}
      <div className={cn(
        "grid gap-5 min-h-0",
        showCreate
          ? "grid-cols-1 lg:grid-cols-[1fr_380px]"
          : "grid-cols-1"
      )}>
        {/* Templates list */}
        <div className="rounded-lg border border-border bg-card overflow-hidden flex flex-col w-full">
          <div className="px-4 py-2.5 border-b border-border bg-muted/40 flex items-center justify-between shrink-0">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Plantillas por evento
            </span>
            <span className="text-xs text-muted-foreground">
              {templates.filter((t) => t.is_enabled).length} / {templates.length} activas
            </span>
          </div>

          <div className="overflow-y-auto">
            {isLoading ? (
              <div className="flex justify-center py-12"><Spinner /></div>
            ) : templates.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <AlertTriangle className="h-8 w-8 opacity-30" />
                <p className="text-sm">No se encontraron plantillas</p>
              </div>
            ) : (
              templates.map((t) => <TemplateRow key={t.id} template={t} />)
            )}
          </div>
        </div>

        {/* Create panel (conditional) */}
        {showCreate && (
          <CreateNotificationPanel onClose={() => setShowCreate(false)} />
        )}
      </div>
    </div>
  );
}
