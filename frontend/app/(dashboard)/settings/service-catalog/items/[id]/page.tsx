"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Save } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";
import {
  useServiceItem,
  useUpdateServiceItem,
  useServiceCategories,
} from "@/hooks/useServiceCatalog";
import { useCasePriorities, useTeams } from "@/hooks/useCases";
import { FormBuilder } from "@/components/organisms/ServiceCatalog/FormBuilder";

export default function ServiceItemPage({ params }: { params: { id: string } }) {
  usePermissionGuard("service_catalog", "read");
  const router = useRouter();

  const { data: item, isLoading } = useServiceItem(params.id);
  const { data: categories = [] } = useServiceCategories();
  const { data: priorities = [] } = useCasePriorities();
  const { data: teams = [] } = useTeams();

  const update = useUpdateServiceItem();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [priorityId, setPriorityId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [defaultLevel, setDefaultLevel] = useState(1);
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (item) {
      setName(item.name);
      setDescription(item.description ?? "");
      setCategoryId(item.category_id);
      setPriorityId(item.default_priority_id ?? "");
      setTeamId(item.default_team_id ?? "");
      setDefaultLevel(item.default_level);
      setIsActive(item.is_active);
    }
  }, [item]);

  async function handleSave() {
    setError(null);
    try {
      await update.mutateAsync({
        id: params.id,
        dto: {
          name,
          description,
          category_id: categoryId,
          default_priority_id: priorityId || null,
          default_team_id: teamId || null,
          default_level: defaultLevel,
          is_active: isActive,
        },
      });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } } };
      setError(e?.response?.data?.message ?? "Error al guardar");
    }
  }

  if (isLoading || !item) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link
          href="/settings/service-catalog"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Volver al catálogo
        </Link>
        <div className="flex items-center justify-between mt-2">
          <div>
            <h1 className="text-xl font-semibold text-foreground">{item.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {item.category_name && <span>{item.category_name} · </span>}
              <span className="font-mono">{item.slug}</span>
            </p>
          </div>
          <Button onClick={handleSave} disabled={update.isPending}>
            <Save className="h-4 w-4" />
            {update.isPending ? "Guardando…" : "Guardar cambios"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* ── Metadata ──────────────────────────────────────────────────────────── */}
      <div className="rounded-lg border border-border bg-card p-5 flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-foreground">Configuración del ítem</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Nombre">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            />
          </Field>

          <Field label="Categoría">
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Descripción">
          <textarea
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
          />
        </Field>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Field label="Prioridad por defecto">
            <select
              value={priorityId}
              onChange={(e) => setPriorityId(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">Sin default</option>
              {priorities.map((p: { id: string; name: string }) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </Field>

          <Field label="Equipo por defecto">
            <select
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">Sin default</option>
              {teams.map((t: { id: string; name: string }) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </Field>

          <Field label="Nivel inicial">
            <input
              type="number"
              min={0}
              max={5}
              value={defaultLevel}
              onChange={(e) => setDefaultLevel(parseInt(e.target.value || "0", 10))}
              className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
            />
          </Field>
        </div>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-foreground">Ítem activo</span>
        </label>
      </div>

      {/* ── Form Builder ──────────────────────────────────────────────────────── */}
      <FormBuilder itemId={params.id} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-foreground">{label}</label>
      {children}
    </div>
  );
}
