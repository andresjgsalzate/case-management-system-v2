"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Trash2, Pencil, Check, X, UserPlus, Users, ChevronDown, ChevronUp,
} from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { Avatar } from "@/components/atoms/Avatar";
import { Badge } from "@/components/atoms/Badge";
import { useConfirm } from "@/components/providers/ConfirmProvider";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TeamMember {
  user_id: string;
  full_name: string | null;
  email: string | null;
  team_role: string;
  joined_at: string;
}

interface Team {
  id: string;
  name: string;
  description: string | null;
  members: TeamMember[];
  created_at: string;
}

interface UserOption {
  id: string;
  full_name: string;
  email: string;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

function useTeams() {
  return useQuery<Team[]>({
    queryKey: ["teams"],
    queryFn: async () => {
      const { data } = await apiClient.get("/teams");
      return data.data ?? [];
    },
  });
}

function useUsers() {
  return useQuery<UserOption[]>({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users");
      return data.data ?? [];
    },
    staleTime: 5 * 60_000,
  });
}

// ── Role badge ────────────────────────────────────────────────────────────────

const ROLE_LABELS: Record<string, string> = {
  manager: "Manager",
  lead: "Lead",
  member: "Miembro",
};

function RoleBadge({ role }: { role: string }) {
  const label = ROLE_LABELS[role] ?? role;
  const color =
    role === "manager" ? "bg-violet-100 text-violet-700 border-violet-200" :
    role === "lead"    ? "bg-blue-100 text-blue-700 border-blue-200" :
                         "bg-muted text-muted-foreground border-border";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

// ── Add member row ────────────────────────────────────────────────────────────

function AddMemberRow({ teamId, existingIds }: { teamId: string; existingIds: Set<string> }) {
  const qc = useQueryClient();
  const { data: users = [] } = useUsers();
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<"manager" | "lead" | "member">("member");

  const addMember = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/teams/${teamId}/members`, { user_id: userId, team_role: role });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teams"] });
      setUserId("");
      setRole("member");
    },
  });

  const available = users.filter((u) => !existingIds.has(u.id));

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border">
      <UserPlus className="h-4 w-4 text-muted-foreground shrink-0" />
      <select
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
        className="flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
      >
        <option value="">Seleccionar usuario…</option>
        {available.map((u) => (
          <option key={u.id} value={u.id}>
            {u.full_name} ({u.email})
          </option>
        ))}
      </select>
      <select
        value={role}
        onChange={(e) => setRole(e.target.value as typeof role)}
        className="w-28 rounded-md border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
      >
        <option value="member">Miembro</option>
        <option value="lead">Lead</option>
        <option value="manager">Manager</option>
      </select>
      <button
        type="button"
        disabled={!userId || addMember.isPending}
        onClick={() => addMember.mutate()}
        className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {addMember.isPending ? <Spinner size="sm" /> : <Plus className="h-3.5 w-3.5" />}
        Agregar
      </button>
    </div>
  );
}

// ── Team card ─────────────────────────────────────────────────────────────────

function TeamCard({ team }: { team: Team }) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(team.name);
  const [editDesc, setEditDesc] = useState(team.description ?? "");

  const updateTeam = useMutation({
    mutationFn: async () => {
      await apiClient.patch(`/teams/${team.id}`, { name: editName, description: editDesc || null });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teams"] });
      setEditing(false);
    },
  });

  const deleteTeam = useMutation({
    mutationFn: async () => {
      await apiClient.delete(`/teams/${team.id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });

  const removeMember = useMutation({
    mutationFn: async (userId: string) => {
      await apiClient.delete(`/teams/${team.id}/members/${userId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });

  async function handleDelete() {
    const ok = await confirm({ description: `¿Eliminar el equipo "${team.name}"? Esta acción no se puede deshacer.` });
    if (ok) deleteTeam.mutate();
  }

  async function handleRemoveMember(userId: string, name: string | null) {
    const ok = await confirm({ description: `¿Quitar a ${name ?? "este usuario"} del equipo?` });
    if (ok) removeMember.mutate(userId);
  }

  const memberIds = new Set(team.members.map((m) => m.user_id));

  return (
    <div className="rounded-lg border border-border bg-card">
      {/* Header */}
      <div className="flex items-start gap-3 p-4">
        <div className="h-10 w-10 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
          <Users className="h-5 w-5 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          {editing ? (
            <div className="flex flex-col gap-2">
              <input
                autoFocus
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="Nombre del equipo"
                className="w-full rounded-md border border-primary bg-background px-3 py-1.5 text-sm focus:outline-none"
              />
              <input
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                placeholder="Descripción (opcional)"
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={!editName.trim() || updateTeam.isPending}
                  onClick={() => updateTeam.mutate()}
                  className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  <Check className="h-3.5 w-3.5" />
                  Guardar
                </button>
                <button
                  type="button"
                  onClick={() => { setEditing(false); setEditName(team.name); setEditDesc(team.description ?? ""); }}
                  className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="font-medium text-foreground">{team.name}</p>
              {team.description && (
                <p className="text-xs text-muted-foreground mt-0.5">{team.description}</p>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {team.members.length} miembro{team.members.length !== 1 ? "s" : ""}
              </p>
            </>
          )}
        </div>

        {!editing && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title={expanded ? "Colapsar" : "Expandir miembros"}
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            <button
              type="button"
              onClick={() => { setEditing(true); setExpanded(true); }}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title="Editar equipo"
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={handleDelete}
              className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
              title="Eliminar equipo"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Members panel */}
      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Miembros
          </p>

          {team.members.length === 0 && (
            <p className="text-sm text-muted-foreground italic py-2">Sin miembros aún</p>
          )}

          <div className="flex flex-col gap-1">
            {team.members.map((m) => (
              <div
                key={m.user_id}
                className="flex items-center gap-3 rounded-md px-2 py-1.5 hover:bg-muted/50 group"
              >
                <Avatar name={m.full_name ?? m.user_id} size="sm" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {m.full_name ?? "Usuario desconocido"}
                  </p>
                  {m.email && (
                    <p className="text-xs text-muted-foreground truncate">{m.email}</p>
                  )}
                </div>
                <RoleBadge role={m.team_role} />
                <button
                  type="button"
                  onClick={() => handleRemoveMember(m.user_id, m.full_name)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-muted-foreground hover:text-destructive transition-all"
                  title="Quitar del equipo"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>

          <AddMemberRow teamId={team.id} existingIds={memberIds} />
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TeamsSettingsPage() {
  const qc = useQueryClient();
  const { data: teams = [], isLoading } = useTeams();
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formError, setFormError] = useState("");

  const createTeam = useMutation({
    mutationFn: async () => {
      await apiClient.post("/teams", { name: formName, description: formDesc || null });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teams"] });
      setShowForm(false);
      setFormName("");
      setFormDesc("");
      setFormError("");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFormError(msg ?? "Error al crear el equipo");
    },
  });

  return (
    <div className="flex flex-col gap-5">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Equipos</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Gestiona equipos y sus miembros para la asignación de casos
          </p>
        </div>
        <button
          type="button"
          onClick={() => { setShowForm((v) => !v); setFormError(""); }}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Nuevo equipo
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Nuevo equipo</p>
          {formError && <p className="text-xs text-destructive">{formError}</p>}
          <div className="flex flex-col gap-2">
            <input
              autoFocus
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Nombre del equipo *"
              className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <input
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="Descripción (opcional)"
              className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={!formName.trim() || createTeam.isPending}
              onClick={() => createTeam.mutate()}
              className="inline-flex items-center gap-1 rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {createTeam.isPending ? <Spinner size="sm" /> : null}
              Crear
            </button>
          </div>
        </div>
      )}

      {/* Team list */}
      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!isLoading && teams.length === 0 && !showForm && (
        <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center">
          <Users className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
          <p className="text-sm font-medium text-foreground">Sin equipos</p>
          <p className="text-xs text-muted-foreground mt-1">
            Crea un equipo para organizar a los agentes y asignarles casos
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {teams.map((team) => (
          <TeamCard key={team.id} team={team} />
        ))}
      </div>
    </div>
  );
}
