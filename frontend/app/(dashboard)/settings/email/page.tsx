// frontend/app/(dashboard)/settings/email/page.tsx
"use client";

import { useState } from "react";
import { Mail, Server, FileCode, Plus, Trash2, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/atoms/Spinner";
import { EmailTemplateEditor } from "@/components/organisms/EmailTemplateEditor";
import {
  useSmtpConfig, useSaveSmtpConfig, useTestSmtpConfig,
  useEmailTemplates, useDeleteEmailTemplate, useUpdateEmailTemplate,
  type EmailTemplate,
} from "@/hooks/useEmailConfig";
import { SCOPE_OPTIONS } from "@/lib/emailRenderer";

type Tab = "smtp" | "templates";

// ── SMTP Form ─────────────────────────────────────────────────────────────────

function SmtpForm() {
  const { data: config, isLoading } = useSmtpConfig();
  const save = useSaveSmtpConfig();
  const test = useTestSmtpConfig();

  const [host, setHost] = useState("");
  const [port, setPort] = useState("587");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [fromName, setFromName] = useState("CaseManager");
  const [useTls, setUseTls] = useState(true);
  const [isEnabled, setIsEnabled] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Populate form once config loads
  if (config && !loaded) {
    setHost(config.host || "");
    setPort(String(config.port || 587));
    setUsername(config.username || "");
    setFromEmail(config.from_email || "");
    setFromName(config.from_name || "CaseManager");
    setUseTls(config.use_tls ?? true);
    setIsEnabled(config.is_enabled ?? false);
    setLoaded(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    await save.mutateAsync({
      host, port: parseInt(port), username: username || null,
      password: password || undefined,
      from_email: fromEmail, from_name: fromName,
      use_tls: useTls, is_enabled: isEnabled,
    });
  }

  async function handleTest() {
    setTestResult(null);
    const result = await test.mutateAsync();
    setTestResult(result);
  }

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>;

  const inputCls = "w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30";

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-5 max-w-xl">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Configuración del servidor SMTP</h2>
        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
          <button
            type="button"
            role="switch"
            aria-checked={isEnabled}
            onClick={() => setIsEnabled(v => !v)}
            className={cn("relative inline-flex h-5 w-9 rounded-full border-2 border-transparent transition-colors", isEnabled ? "bg-primary" : "bg-muted-foreground/30")}
          >
            <span className={cn("inline-block h-4 w-4 rounded-full bg-white shadow transition-all", isEnabled ? "translate-x-4" : "translate-x-0")} />
          </button>
          {isEnabled ? "Habilitado" : "Deshabilitado"}
        </label>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2 flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Servidor SMTP</label>
          <input type="text" value={host} onChange={e => setHost(e.target.value)} placeholder="smtp.gmail.com" className={inputCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Puerto</label>
          <input type="number" value={port} onChange={e => setPort(e.target.value)} className={inputCls} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Usuario</label>
          <input type="text" value={username} onChange={e => setUsername(e.target.value)} placeholder="usuario@empresa.com" className={inputCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Contraseña</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Dejar vacío para no cambiar" className={inputCls} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Nombre del remitente</label>
          <input type="text" value={fromName} onChange={e => setFromName(e.target.value)} placeholder="CaseManager" className={inputCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Email del remitente</label>
          <input type="email" value={fromEmail} onChange={e => setFromEmail(e.target.value)} placeholder="noreply@empresa.com" className={inputCls} />
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer w-fit">
        <input type="checkbox" checked={useTls} onChange={e => setUseTls(e.target.checked)} className="rounded border-border" />
        Usar STARTTLS
      </label>

      {testResult && (
        <div className={cn(
          "flex items-start gap-2 rounded-md border p-3 text-sm",
          testResult.success ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-red-50 border-red-200 text-red-700"
        )}>
          {testResult.success
            ? <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
            : <XCircle className="h-4 w-4 shrink-0 mt-0.5" />}
          {testResult.message}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={save.isPending}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {save.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Guardar configuración
        </button>
        <button
          type="button"
          onClick={handleTest}
          disabled={test.isPending || !host}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md border border-border text-sm hover:bg-muted disabled:opacity-50 transition-colors"
        >
          {test.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Server className="h-3.5 w-3.5" />}
          Probar conexión
        </button>
      </div>
    </form>
  );
}

// ── Templates list ────────────────────────────────────────────────────────────

function TemplatesList({ onEdit }: { onEdit: (t: EmailTemplate | null) => void }) {
  const { data: templates = [], isLoading } = useEmailTemplates();
  const deleteT = useDeleteEmailTemplate();
  const updateT = useUpdateEmailTemplate();

  const scopeLabel = (scope: string) =>
    SCOPE_OPTIONS.find(o => o.value === scope)?.label ?? scope;

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Plantillas de correo</h2>
        <button
          type="button"
          onClick={() => onEdit(null)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Nueva plantilla
        </button>
      </div>

      {templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2">
          <FileCode className="h-10 w-10 opacity-20" />
          <p className="text-sm">Sin plantillas aún. Crea una para empezar.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-border divide-y divide-border overflow-hidden">
          {templates.map(t => (
            <div key={t.id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/30 transition-colors">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{t.name}</p>
                <p className="text-xs text-muted-foreground">{scopeLabel(t.scope)} · {t.blocks.length} bloques</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  role="switch"
                  aria-checked={t.is_active}
                  onClick={() => updateT.mutate({ id: t.id, is_active: !t.is_active })}
                  title={t.is_active ? "Desactivar" : "Activar"}
                  className={cn(
                    "relative inline-flex h-5 w-9 rounded-full border-2 border-transparent transition-colors",
                    t.is_active ? "bg-primary" : "bg-muted-foreground/30"
                  )}
                >
                  <span className={cn("inline-block h-4 w-4 rounded-full bg-white shadow transition-all", t.is_active ? "translate-x-4" : "translate-x-0")} />
                </button>
                <button
                  type="button"
                  onClick={() => onEdit(t)}
                  className="px-2 py-1 text-xs border border-border rounded-md hover:bg-muted text-muted-foreground transition-colors"
                >
                  Editar
                </button>
                <button
                  type="button"
                  onClick={() => deleteT.mutate(t.id)}
                  className="p-1 text-muted-foreground hover:text-destructive transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EmailSettingsPage() {
  const [tab, setTab] = useState<Tab>("smtp");
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null | undefined>(undefined);
  // undefined = no editor open, null = creating new, EmailTemplate = editing

  if (editingTemplate !== undefined) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex flex-col">
        <EmailTemplateEditor
          template={editingTemplate ?? undefined}
          onClose={() => setEditingTemplate(undefined)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Configuración de Email</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Servidor SMTP y plantillas HTML para notificaciones por correo.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-0">
        {([["smtp", "Servidor SMTP"], ["templates", "Plantillas de correo"]] as [Tab, string][]).map(([t, label]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card p-5">
        {tab === "smtp" && <SmtpForm />}
        {tab === "templates" && (
          <TemplatesList onEdit={(t) => setEditingTemplate(t === null ? null : t)} />
        )}
      </div>
    </div>
  );
}
