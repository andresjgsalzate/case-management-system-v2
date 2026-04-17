"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import {
  Tag, Plus, Pencil, Trash2, X, FolderOpen, Check,
  Calendar, Hash, FileText, LayoutGrid, TrendingUp,
} from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { SearchBar } from "@/components/molecules/SearchBar";
import { Spinner } from "@/components/atoms/Spinner";
import { cn } from "@/lib/utils";
import type { Disposition, DispositionCategory, ApiResponse } from "@/lib/types";

// ── Types ──────────────────────────────────────────────────────────────────────

interface OpenCase {
  id: string;
  case_number: string;
  title: string;
  application_name?: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const MONTHS = [
  "Enero","Febrero","Marzo","Abril","Mayo","Junio",
  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
];

function periodLabel(period: string) {
  const [year, month] = period.split("-");
  return `${MONTHS[parseInt(month, 10) - 1]} ${year}`;
}

function dispositionPeriod(d: Disposition): string {
  const ref = d.date ?? d.created_at?.slice(0, 10) ?? "";
  if (!ref) return "Sin fecha";
  return ref.slice(0, 7); // "YYYY-MM"
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useCategories() {
  return useQuery<DispositionCategory[]>({
    queryKey: ["disposition-categories"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<DispositionCategory[]>>("/dispositions/categories");
      return data.data ?? [];
    },
  });
}

function useOpenCases() {
  return useQuery<OpenCase[]>({
    queryKey: ["open-cases-for-dispositions"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: OpenCase[] }>("/cases", {
        params: { page_size: 100, page: 1 },
      });
      return Array.isArray(data.data) ? data.data : [];
    },
    staleTime: 2 * 60_000,
  });
}

function useAllDispositions() {
  return useQuery<Disposition[]>({
    queryKey: ["dispositions-all"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Disposition[]>>("/dispositions");
      return data.data ?? [];
    },
  });
}

function useSearchDispositions(q: string) {
  return useQuery<Disposition[]>({
    queryKey: ["dispositions-search", q],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Disposition[]>>("/dispositions", {
        params: { q },
      });
      return data.data ?? [];
    },
    enabled: q.length > 1,
  });
}

function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiClient.post("/dispositions/categories", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disposition-categories"] }),
  });
}

function useCreateDisposition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: object) => apiClient.post("/dispositions", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispositions-all"] }),
  });
}

function useUpdateDisposition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
      apiClient.patch(`/dispositions/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispositions-all"] }),
  });
}

function useDeleteDisposition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/dispositions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispositions-all"] }),
  });
}

// ── Category modal ────────────────────────────────────────────────────────────

function CategoryModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useCreateCategory();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync({ name: name.trim(), description: description.trim() || undefined });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-sm mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">Nueva categoría</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-5 py-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Nombre *</label>
            <input
              autoFocus type="text" value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ej: Scripts, Desarrollos, Configuraciones"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Descripción</label>
            <input
              type="text" value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Opcional"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors">
              Cancelar
            </button>
            <button
              type="submit" disabled={!name.trim() || create.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {create.isPending ? <Spinner size="sm" /> : <Check className="h-3.5 w-3.5" />}
              Crear
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Disposition modal ─────────────────────────────────────────────────────────

interface DispositionFormData {
  category_id: string;
  date: string;
  case_number: string;
  item_name: string;
  storage_path: string;
  revision_number: string;
  observations: string;
}

function DispositionModal({
  categories,
  openCases,
  editing,
  onClose,
}: {
  categories: DispositionCategory[];
  openCases: OpenCase[];
  editing?: Disposition;
  onClose: () => void;
}) {
  const [form, setForm] = useState<DispositionFormData>({
    category_id: editing?.category_id ?? categories[0]?.id ?? "",
    date: editing?.date ?? new Date().toISOString().slice(0, 10),
    case_number: editing?.case_number ?? "",
    item_name: editing?.item_name ?? "",
    storage_path: editing?.storage_path ?? "",
    revision_number: editing?.revision_number ?? "",
    observations: editing?.observations ?? "",
  });

  const create = useCreateDisposition();
  const update = useUpdateDisposition();
  const isPending = create.isPending || update.isPending;

  function set(field: keyof DispositionFormData) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm(prev => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.category_id || !form.case_number.trim() || !form.item_name.trim()) return;
    const payload = {
      category_id: form.category_id,
      date: form.date || null,
      case_number: form.case_number.trim(),
      item_name: form.item_name.trim(),
      storage_path: form.storage_path.trim() || null,
      revision_number: form.revision_number.trim() || null,
      observations: form.observations.trim() || null,
    };
    if (editing) {
      await update.mutateAsync({ id: editing.id, ...payload });
    } else {
      await create.mutateAsync(payload);
    }
    onClose();
  }

  const inputCls = "w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30";
  const labelCls = "text-xs font-medium text-muted-foreground";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border sticky top-0 bg-card z-10">
          <h2 className="text-sm font-semibold text-foreground">
            {editing ? "Editar disposición" : "Nueva disposición"}
          </h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-5 py-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className={labelCls}>Fecha *</label>
              <input type="date" value={form.date} onChange={set("date")} className={inputCls} />
            </div>
            <div className="flex flex-col gap-1">
              <label className={labelCls}>Categoría *</label>
              {categories.length === 0 ? (
                <p className="text-xs text-amber-600 pt-2">Crea una categoría primero.</p>
              ) : (
                <select value={form.category_id} onChange={set("category_id")} className={inputCls}>
                  {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Número de caso *</label>
            <select value={form.case_number} onChange={set("case_number")} className={inputCls}>
              <option value="">Selecciona un caso…</option>
              {openCases.map(c => (
                <option key={c.id} value={c.case_number}>
                  {c.case_number} — {c.title}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Nombre del script / desarrollo *</label>
            <input
              type="text" value={form.item_name} onChange={set("item_name")}
              placeholder="Ej: script_migracion_clientes.sql"
              className={inputCls}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Ruta de almacenamiento</label>
            <input
              type="text" value={form.storage_path} onChange={set("storage_path")}
              placeholder="Ej: /repos/scripts/2026/abril/"
              className={inputCls}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Número de revisión (SVN / GitHub)</label>
            <input
              type="text" value={form.revision_number} onChange={set("revision_number")}
              placeholder="Ej: r1234 o abc1234"
              className={inputCls}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className={labelCls}>Observaciones</label>
            <textarea
              value={form.observations} onChange={set("observations")}
              placeholder="Notas adicionales…"
              rows={3}
              className={cn(inputCls, "resize-none")}
            />
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted transition-colors">
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!form.category_id || !form.case_number.trim() || !form.item_name.trim() || isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {isPending ? <Spinner size="sm" /> : <Check className="h-3.5 w-3.5" />}
              {editing ? "Guardar cambios" : "Crear disposición"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Case detail modal ─────────────────────────────────────────────────────────

function CaseDetailModal({
  caseNumber,
  applicationName,
  dispositions,
  categories,
  onEdit,
  onDelete,
  onClose,
}: {
  caseNumber: string;
  applicationName: string;
  dispositions: Disposition[];
  categories: DispositionCategory[];
  onEdit: (d: Disposition) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const categoryName = (id: string) => categories.find(c => c.id === id)?.name ?? "—";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-border shrink-0">
          <div>
            <p className="text-sm font-semibold text-foreground">{caseNumber}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{applicationName}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground bg-muted rounded-full px-2.5 py-1 tabular-nums">
              {dispositions.length} {dispositions.length !== 1 ? "disposiciones" : "disposición"}
            </span>
            <button
              type="button" onClick={onClose}
              className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* List */}
        <div className="overflow-y-auto flex-1 px-4 py-3 flex flex-col gap-3">
          {dispositions.map(d => (
            <div key={d.id} className="rounded-lg border border-border bg-background p-4 flex items-start gap-3 group hover:border-primary/30 transition-colors">
              <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                <FileText className="h-4 w-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground">
                  {d.item_name ?? d.title ?? "—"}
                </p>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1">
                  {d.date && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      {d.date}
                    </span>
                  )}
                  {d.revision_number && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Hash className="h-3 w-3" />
                      {d.revision_number}
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground/60">{categoryName(d.category_id)}</span>
                </div>
                {d.storage_path && (
                  <p className="text-xs text-muted-foreground mt-1 break-all" title={d.storage_path}>
                    {d.storage_path}
                  </p>
                )}
                {d.observations && (
                  <p className="text-xs text-muted-foreground mt-1 italic">{d.observations}</p>
                )}
              </div>
              <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button" onClick={() => onEdit(d)} title="Editar"
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button" onClick={() => onDelete(d.id)} title="Eliminar"
                  className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Case group card (inside a month column) ───────────────────────────────────

function CaseGroupCard({
  caseNumber,
  applicationName,
  count,
  onClick,
}: {
  caseNumber: string;
  applicationName: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-lg border border-border bg-background p-3 text-left hover:border-primary/40 hover:bg-primary/5 transition-all group"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="h-6 w-6 rounded bg-primary/10 flex items-center justify-center shrink-0">
            <Tag className="h-3 w-3 text-primary" />
          </div>
          <span className="text-xs font-semibold text-foreground truncate">{caseNumber}</span>
        </div>
        <span className="text-xs font-semibold tabular-nums bg-muted text-muted-foreground rounded-full px-2 py-0.5 shrink-0 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
          {count}
        </span>
      </div>
      <p className="text-xs text-muted-foreground mt-1.5 truncate">{applicationName}</p>
    </button>
  );
}

// ── Month column ──────────────────────────────────────────────────────────────

function MonthColumn({
  period,
  dispositions,
  categories,
  caseAppMap,
  onEdit,
  onDelete,
}: {
  period: string;
  dispositions: Disposition[];
  categories: DispositionCategory[];
  caseAppMap: Record<string, string>;
  onEdit: (d: Disposition) => void;
  onDelete: (id: string) => void;
}) {
  const [selectedCase, setSelectedCase] = useState<string | null>(null);

  // Group dispositions by case_number within this month
  const caseGroups = useMemo(() => {
    const map = new Map<string, Disposition[]>();
    for (const d of dispositions) {
      const key = d.case_number ?? "(sin caso)";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(d);
    }
    return Array.from(map.entries()).sort(([, a], [, b]) => b.length - a.length);
  }, [dispositions]);

  return (
    <>
      <div className="flex flex-col gap-2 min-w-[240px] w-[240px]">
        {/* Column header */}
        <div className="flex items-center justify-between px-1">
          <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
            {periodLabel(period)}
          </h3>
          <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5 tabular-nums">
            {dispositions.length}
          </span>
        </div>

        {/* Case group cards */}
        <div className="flex flex-col gap-2 bg-muted/30 rounded-xl p-2 border border-border/60 min-h-[80px]">
          {caseGroups.map(([cn, disps]) => (
            <CaseGroupCard
              key={cn}
              caseNumber={cn}
              applicationName={caseAppMap[cn] ?? "Sin aplicación"}
              count={disps.length}
              onClick={() => setSelectedCase(cn)}
            />
          ))}
        </div>
      </div>

      {/* Detail modal for selected case */}
      {selectedCase && (() => {
        const disps = caseGroups.find(([cn]) => cn === selectedCase)?.[1] ?? [];
        return (
          <CaseDetailModal
            caseNumber={selectedCase}
            applicationName={caseAppMap[selectedCase] ?? "Sin aplicación"}
            dispositions={disps}
            categories={categories}
            onEdit={d => { setSelectedCase(null); onEdit(d); }}
            onDelete={id => { onDelete(id); }}
            onClose={() => setSelectedCase(null)}
          />
        );
      })()}
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DispositionsPage() {
  usePermissionGuard("dispositions", "read");
  const [search, setSearch] = useState("");
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showDispositionModal, setShowDispositionModal] = useState(false);
  const [editing, setEditing] = useState<Disposition | undefined>(undefined);

  const { data: categories = [] } = useCategories();
  const { data: openCases = [] } = useOpenCases();
  const { data: allDispositions = [], isLoading } = useAllDispositions();
  const { data: searchResults = [], isLoading: searchLoading } = useSearchDispositions(search);
  const deleteDisposition = useDeleteDisposition();

  const isSearching = search.length > 1;

  // Map case_number → application_name from the open cases list
  const caseAppMap = useMemo(
    () => Object.fromEntries(openCases.map(c => [c.case_number, c.application_name ?? "Sin aplicación"])),
    [openCases]
  );

  // Group all dispositions by period (YYYY-MM), sorted newest first
  const grouped = useMemo(() => {
    const map = new Map<string, Disposition[]>();
    for (const d of allDispositions) {
      const p = dispositionPeriod(d);
      if (!map.has(p)) map.set(p, []);
      map.get(p)!.push(d);
    }
    return Array.from(map.entries()).sort(([a], [b]) => b.localeCompare(a));
  }, [allDispositions]);

  // ── Stats derived from allDispositions ──────────────────────────────────────
  const stats = useMemo(() => {
    const currentPeriod = new Date().toISOString().slice(0, 7); // "YYYY-MM"
    const thisMonth = allDispositions.filter(d => dispositionPeriod(d) === currentPeriod);

    // Count by application for current month
    const byApp = new Map<string, number>();
    for (const d of thisMonth) {
      const app = caseAppMap[d.case_number ?? ""] ?? "Sin aplicación";
      byApp.set(app, (byApp.get(app) ?? 0) + 1);
    }
    const topApps = Array.from(byApp.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);

    // Previous month comparison
    const prevDate = new Date();
    prevDate.setMonth(prevDate.getMonth() - 1);
    const prevPeriod = prevDate.toISOString().slice(0, 7);
    const prevMonthCount = allDispositions.filter(d => dispositionPeriod(d) === prevPeriod).length;

    return {
      totalThisMonth: thisMonth.length,
      totalAll: allDispositions.length,
      topApps,
      prevMonthCount,
      currentPeriodLabel: periodLabel(currentPeriod),
    };
  }, [allDispositions, caseAppMap]);

  function openEdit(d: Disposition) {
    setEditing(d);
    setShowDispositionModal(true);
  }

  function closeDispositionModal() {
    setShowDispositionModal(false);
    setEditing(undefined);
  }

  const categoryName = (id: string) => categories.find(c => c.id === id)?.name ?? "—";

  return (
    <div className="flex flex-col gap-5 h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Disposiciones</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Registro técnico de scripts, desarrollos y cambios por caso
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowCategoryModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted text-muted-foreground transition-colors"
          >
            <FolderOpen className="h-3.5 w-3.5" />
            Nueva categoría
          </button>
          <button
            type="button"
            onClick={() => { setEditing(undefined); setShowDispositionModal(true); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Nueva disposición
          </button>
        </div>
      </div>

      {/* Stats */}
      {!isLoading && allDispositions.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">
          {/* Total este mes */}
          <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Este mes</span>
              <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
                <Calendar className="h-3.5 w-3.5 text-primary" />
              </div>
            </div>
            <p className="text-2xl font-bold text-foreground tabular-nums">{stats.totalThisMonth}</p>
            <p className="text-xs text-muted-foreground">{stats.currentPeriodLabel}</p>
            {stats.prevMonthCount > 0 && (
              <p className="text-xs text-muted-foreground/70 mt-0.5 flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                {stats.prevMonthCount} el mes anterior
              </p>
            )}
          </div>

          {/* Total acumulado */}
          <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Total acumulado</span>
              <div className="h-7 w-7 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                <LayoutGrid className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              </div>
            </div>
            <p className="text-2xl font-bold text-foreground tabular-nums">{stats.totalAll}</p>
            <p className="text-xs text-muted-foreground">en {grouped.length} {grouped.length !== 1 ? "meses" : "mes"}</p>
          </div>

          {/* Por aplicación este mes */}
          <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-2 col-span-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Por aplicación — {stats.currentPeriodLabel}</span>
              <div className="h-7 w-7 rounded-lg bg-violet-500/10 flex items-center justify-center">
                <Tag className="h-3.5 w-3.5 text-violet-600 dark:text-violet-400" />
              </div>
            </div>
            {stats.topApps.length === 0 ? (
              <p className="text-xs text-muted-foreground/60">Sin registros este mes.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {stats.topApps.map(([app, count]) => {
                  const pct = Math.round((count / stats.totalThisMonth) * 100);
                  return (
                    <div key={app} className="flex items-center gap-2">
                      <span className="text-xs text-foreground truncate flex-1 min-w-0">{app}</span>
                      <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden shrink-0">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold tabular-nums text-foreground w-4 text-right shrink-0">{count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Search */}
      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Buscar por caso, script, observaciones…"
        className="max-w-sm shrink-0"
      />

      {/* Loading */}
      {(isLoading || (isSearching && searchLoading)) && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {/* Search results — flat list */}
      {!isLoading && isSearching && !searchLoading && (
        <>
          {searchResults.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
              <Tag className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">Sin resultados para esa búsqueda.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {searchResults.map(d => (
                <div key={d.id} className="rounded-lg border border-border bg-card p-4 flex items-start gap-3 group hover:border-primary/30 transition-colors">
                  <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground">{d.item_name ?? d.title ?? "—"}</p>
                    <p className="text-xs text-primary/80 font-medium mt-0.5">{d.case_number}</p>
                    <p className="text-xs text-muted-foreground">{caseAppMap[d.case_number ?? ""] ?? "Sin aplicación"}</p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1">
                      {d.date && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Calendar className="h-3 w-3" />{d.date}
                        </span>
                      )}
                      {d.revision_number && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Hash className="h-3 w-3" />{d.revision_number}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground/60">{categoryName(d.category_id)}</span>
                    </div>
                    {d.storage_path && <p className="text-xs text-muted-foreground mt-1 truncate">{d.storage_path}</p>}
                    {d.observations && <p className="text-xs text-muted-foreground mt-1 italic">{d.observations}</p>}
                  </div>
                  <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button type="button" onClick={() => openEdit(d)} title="Editar"
                      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button type="button" onClick={() => deleteDisposition.mutate(d.id)} title="Eliminar"
                      className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Columnas por mes — scroll horizontal */}
      {!isLoading && !isSearching && (
        <>
          {grouped.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center text-muted-foreground">
              <Tag className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No hay disposiciones aún. Crea una para empezar.</p>
            </div>
          ) : (
            <div className="overflow-x-auto pb-4 -mx-1 px-1">
              <div className="flex gap-4 w-max">
                {grouped.map(([period, dispositions]) => (
                  <MonthColumn
                    key={period}
                    period={period}
                    dispositions={dispositions}
                    categories={categories}
                    caseAppMap={caseAppMap}
                    onEdit={openEdit}
                    onDelete={id => deleteDisposition.mutate(id)}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Modals */}
      {showCategoryModal && (
        <CategoryModal onClose={() => setShowCategoryModal(false)} />
      )}
      {showDispositionModal && (
        <DispositionModal
          categories={categories}
          openCases={openCases}
          editing={editing}
          onClose={closeDispositionModal}
        />
      )}
    </div>
  );
}
