"use client";

import { ArrowLeft, Pencil, Plus, Trash2, X, Check } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import { useHasPermission } from "@/hooks/useHasPermission";
import { useCasePriorities } from "@/hooks/useCases";
import type { CasePriority } from "@/lib/types";
import {
  useCreateSlaPolicy,
  useCreateToolAction,
  useCreateToolType,
  useDeleteSlaPolicy,
  useDeleteToolAction,
  useDeleteToolType,
  useSlaPoliciesAdmin,
  useToolActionsAdmin,
  useToolTypesAdmin,
  useUpdateSlaPolicy,
  useUpdateToolAction,
  useUpdateToolType,
} from "@/hooks/useTriageCatalogsAdmin";

type Tab = "tool-types" | "tool-actions" | "sla-policies";

const TABS: { key: Tab; label: string }[] = [
  { key: "tool-types", label: "Tipos de herramienta" },
  { key: "tool-actions", label: "Acciones aplicadas" },
  { key: "sla-policies", label: "Políticas SLA" },
];

export default function TriageCatalogsPage() {
  usePermissionGuard("security_taxonomies", "read");
  const canManage = useHasPermission("security_taxonomies", "manage_global");
  const [tab, setTab] = useState<Tab>("tool-types");

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <div>
        <Link
          href="/settings"
          className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Configuración
        </Link>
        <h1 className="text-xl font-semibold text-foreground">
          Catálogos de Triage
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Listas parametrizables que alimentan el formulario de triage SOC:
          tipos de herramienta, acciones aplicadas y políticas de SLA por
          prioridad.
        </p>
      </div>

      {!canManage && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
          Solo lectura — requiere permiso{" "}
          <code className="text-[11px]">security_taxonomies:manage_global</code>{" "}
          para editar.
        </p>
      )}

      <nav className="flex flex-wrap gap-1 border-b">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`border-b-2 px-3 py-1.5 text-sm transition-colors ${
              tab === t.key
                ? "border-primary font-medium text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "tool-types" && <ToolTypesTab canManage={canManage} />}
      {tab === "tool-actions" && <ToolActionsTab canManage={canManage} />}
      {tab === "sla-policies" && <SlaPoliciesTab canManage={canManage} />}
    </div>
  );
}

// ─── Tool types tab ─────────────────────────────────────────────

function ToolTypesTab({ canManage }: { canManage: boolean }) {
  const { data: rows = [], isLoading } = useToolTypesAdmin();
  const create = useCreateToolType();
  const update = useUpdateToolType();
  const del = useDeleteToolType();

  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  async function handleAdd() {
    if (!newName.trim()) return;
    await create.mutateAsync({ name: newName.trim() }).catch(() => {});
    setNewName("");
  }

  return (
    <div className="space-y-3">
      {canManage && (
        <div className="flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Nuevo tipo de herramienta (ej. Cloud WAF)"
            className="flex-1 rounded border bg-background px-2 py-1.5 text-sm"
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={!newName.trim() || create.isPending}
            className="inline-flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> Agregar
          </button>
        </div>
      )}
      {create.isError && (
        <p className="text-xs text-rose-600">{create.error.message}</p>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <ul className="divide-y rounded border">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              {editingId === r.id ? (
                <>
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="flex-1 rounded border bg-background px-2 py-1 text-sm"
                  />
                  <IconBtn
                    title="Guardar"
                    onClick={async () => {
                      await update
                        .mutateAsync({ id: r.id, body: { name: editName.trim() } })
                        .catch(() => {});
                      setEditingId(null);
                    }}
                  >
                    <Check className="h-4 w-4 text-emerald-600" />
                  </IconBtn>
                  <IconBtn title="Cancelar" onClick={() => setEditingId(null)}>
                    <X className="h-4 w-4" />
                  </IconBtn>
                </>
              ) : (
                <>
                  <span className={`flex-1 ${r.is_active ? "" : "text-muted-foreground line-through"}`}>
                    {r.name}
                    {!r.is_active && (
                      <span className="ml-2 text-[10px] uppercase">inactivo</span>
                    )}
                  </span>
                  {canManage && (
                    <>
                      {!r.is_active && (
                        <IconBtn
                          title="Reactivar"
                          onClick={() =>
                            update.mutate({ id: r.id, body: { is_active: true } })
                          }
                        >
                          <Check className="h-4 w-4 text-emerald-600" />
                        </IconBtn>
                      )}
                      <IconBtn
                        title="Editar"
                        onClick={() => {
                          setEditingId(r.id);
                          setEditName(r.name);
                        }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </IconBtn>
                      {r.is_active && (
                        <IconBtn title="Desactivar" onClick={() => del.mutate(r.id)}>
                          <Trash2 className="h-3.5 w-3.5 text-rose-600" />
                        </IconBtn>
                      )}
                    </>
                  )}
                </>
              )}
            </li>
          ))}
          {rows.length === 0 && (
            <li className="px-3 py-4 text-center text-sm text-muted-foreground">
              Sin tipos de herramienta.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

// ─── Tool actions tab ───────────────────────────────────────────

function ToolActionsTab({ canManage }: { canManage: boolean }) {
  const { data: rows = [], isLoading } = useToolActionsAdmin();
  const create = useCreateToolAction();
  const update = useUpdateToolAction();
  const del = useDeleteToolAction();

  const [newName, setNewName] = useState("");

  async function handleAdd() {
    if (!newName.trim()) return;
    await create.mutateAsync({ name: newName.trim() }).catch(() => {});
    setNewName("");
  }

  return (
    <div className="space-y-3">
      {canManage && (
        <div className="flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Nueva acción (ej. Contención automática)"
            className="flex-1 rounded border bg-background px-2 py-1.5 text-sm"
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={!newName.trim() || create.isPending}
            className="inline-flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> Agregar
          </button>
        </div>
      )}
      {create.isError && (
        <p className="text-xs text-rose-600">{create.error.message}</p>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <ul className="divide-y rounded border">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className={`flex-1 ${r.is_active ? "" : "text-muted-foreground line-through"}`}>
                {r.name}
                {!r.is_active && (
                  <span className="ml-2 text-[10px] uppercase">inactivo</span>
                )}
              </span>
              {canManage && r.is_active && (
                <IconBtn title="Desactivar" onClick={() => del.mutate(r.id)}>
                  <Trash2 className="h-3.5 w-3.5 text-rose-600" />
                </IconBtn>
              )}
              {canManage && !r.is_active && (
                <IconBtn
                  title="Reactivar"
                  onClick={() => update.mutate({ id: r.id, body: { is_active: true } })}
                >
                  <Check className="h-4 w-4 text-emerald-600" />
                </IconBtn>
              )}
            </li>
          ))}
          {rows.length === 0 && (
            <li className="px-3 py-4 text-center text-sm text-muted-foreground">
              Sin acciones.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

// ─── SLA policies tab ───────────────────────────────────────────

function SlaPoliciesTab({ canManage }: { canManage: boolean }) {
  const { data: policies = [], isLoading } = useSlaPoliciesAdmin();
  const { data: prioritiesRaw = [] } = useCasePriorities();
  const priorities = prioritiesRaw as CasePriority[];
  const create = useCreateSlaPolicy();
  const update = useUpdateSlaPolicy();
  const del = useDeleteSlaPolicy();

  const priorityName = (id: string) =>
    priorities.find((p) => p.id === id)?.name ?? id;

  // Priorities without a policy yet (so we don't offer duplicates)
  const unmapped = priorities.filter(
    (p) => !policies.some((pol) => pol.priority_id === p.id),
  );
  const [newPriorityId, setNewPriorityId] = useState("");
  const [newMinutes, setNewMinutes] = useState("");

  async function handleAdd() {
    if (!newPriorityId) return;
    await create
      .mutateAsync({
        priority_id: newPriorityId,
        sla_minutes: newMinutes === "" ? null : Number(newMinutes),
      })
      .catch(() => {});
    setNewPriorityId("");
    setNewMinutes("");
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Minutos de SLA de notificación por prioridad. Dejá el campo vacío
        para N/A (ej. Falso Positivo).
      </p>

      {canManage && unmapped.length > 0 && (
        <div className="flex gap-2">
          <select
            value={newPriorityId}
            onChange={(e) => setNewPriorityId(e.target.value)}
            className="flex-1 rounded border bg-background px-2 py-1.5 text-sm"
          >
            <option value="">— prioridad —</option>
            {unmapped.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            value={newMinutes}
            onChange={(e) => setNewMinutes(e.target.value)}
            placeholder="min (vacío=N/A)"
            className="w-32 rounded border bg-background px-2 py-1.5 text-sm"
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={!newPriorityId || create.isPending}
            className="inline-flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> Agregar
          </button>
        </div>
      )}
      {create.isError && (
        <p className="text-xs text-rose-600">{create.error.message}</p>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : (
        <ul className="divide-y rounded border">
          {policies.map((pol) => (
            <SlaRow
              key={pol.id}
              priorityName={priorityName(pol.priority_id)}
              minutes={pol.sla_minutes}
              canManage={canManage}
              onSave={(m) => update.mutate({ id: pol.id, body: { sla_minutes: m } })}
              onDelete={() => del.mutate(pol.id)}
            />
          ))}
          {policies.length === 0 && (
            <li className="px-3 py-4 text-center text-sm text-muted-foreground">
              Sin políticas SLA.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function SlaRow({
  priorityName, minutes, canManage, onSave, onDelete,
}: {
  priorityName: string;
  minutes: number | null;
  canManage: boolean;
  onSave: (m: number | null) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(minutes == null ? "" : String(minutes));

  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <span className="flex-1 font-medium">{priorityName}</span>
      {editing ? (
        <>
          <input
            type="number"
            min={0}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            placeholder="N/A"
            className="w-24 rounded border bg-background px-2 py-1 text-sm"
          />
          <IconBtn
            title="Guardar"
            onClick={() => {
              onSave(val === "" ? null : Number(val));
              setEditing(false);
            }}
          >
            <Check className="h-4 w-4 text-emerald-600" />
          </IconBtn>
          <IconBtn title="Cancelar" onClick={() => setEditing(false)}>
            <X className="h-4 w-4" />
          </IconBtn>
        </>
      ) : (
        <>
          <span className="text-muted-foreground">
            {minutes == null ? "N/A" : `${minutes} min`}
          </span>
          {canManage && (
            <>
              <IconBtn title="Editar" onClick={() => setEditing(true)}>
                <Pencil className="h-3.5 w-3.5" />
              </IconBtn>
              <IconBtn title="Eliminar" onClick={onDelete}>
                <Trash2 className="h-3.5 w-3.5 text-rose-600" />
              </IconBtn>
            </>
          )}
        </>
      )}
    </li>
  );
}

function IconBtn({
  title, onClick, children,
}: {
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="rounded p-1 hover:bg-muted"
    >
      {children}
    </button>
  );
}
