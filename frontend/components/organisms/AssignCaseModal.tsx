"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Users, X, Check, UserCheck } from "lucide-react";
import { useTeams, useUsers, useAssignCase } from "@/hooks/useCases";
import { Avatar } from "@/components/atoms/Avatar";
import { Spinner } from "@/components/atoms/Spinner";

interface Props {
  caseId: string;
  currentAssignedTo: string | null;
  currentTeamId?: string | null;
  trigger: React.ReactNode;
  onAssigned?: () => void;
}

export function AssignCaseModal({ caseId, currentAssignedTo, currentTeamId, trigger, onAssigned }: Props) {
  const [open, setOpen] = useState(false);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(currentTeamId ?? null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(currentAssignedTo);
  const [error, setError] = useState<string | null>(null);

  const { data: teams = [], isLoading: loadingTeams } = useTeams();
  const { data: users = [], isLoading: loadingUsers } = useUsers();
  const assign = useAssignCase(caseId);

  // When a team is selected use its members (already enriched with names from backend).
  // When no team is selected show all users.
  const visibleUsers: { id: string; full_name: string; email: string }[] = selectedTeamId
    ? (teams.find((t) => t.id === selectedTeamId)?.members ?? [])
        .filter((m) => m.full_name)
        .map((m) => ({ id: m.user_id, full_name: m.full_name!, email: m.email ?? "" }))
    : users;

  function resetAndOpen() {
    setSelectedTeamId(currentTeamId ?? null);
    setSelectedUserId(currentAssignedTo);
    setError(null);
    setOpen(true);
  }

  async function handleSubmit() {
    setError(null);
    try {
      await assign.mutateAsync({
        assigned_to: selectedUserId,
        team_id: selectedTeamId,
      });
      setOpen(false);
      onAssigned?.();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(e?.response?.data?.message ?? e?.response?.data?.detail ?? "Error al asignar el caso");
    }
  }

  const isLoading = loadingTeams || loadingUsers;

  return (
    <Dialog.Root open={open} onOpenChange={(v) => { if (v) resetAndOpen(); else setOpen(false); }}>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm animate-in fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card shadow-xl animate-in fade-in-0 zoom-in-95">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div className="flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-primary" />
              <Dialog.Title className="text-base font-semibold text-foreground">
                Asignar caso
              </Dialog.Title>
            </div>
            <Dialog.Close className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Spinner />
            </div>
          ) : (
            <div className="px-5 py-4 flex flex-col gap-5">
              {/* Team selector */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Equipo
                </p>
                <div className="flex flex-wrap gap-2">
                  {/* "Sin equipo" chip */}
                  <button
                    type="button"
                    onClick={() => { setSelectedTeamId(null); setSelectedUserId(null); }}
                    className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors ${
                      selectedTeamId === null
                        ? "border-primary bg-primary/10 text-primary font-medium"
                        : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                    }`}
                  >
                    {selectedTeamId === null && <Check className="h-3 w-3" />}
                    Sin equipo
                  </button>

                  {teams.map((team) => (
                    <button
                      key={team.id}
                      type="button"
                      onClick={() => { setSelectedTeamId(team.id); setSelectedUserId(null); }}
                      className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors ${
                        selectedTeamId === team.id
                          ? "border-primary bg-primary/10 text-primary font-medium"
                          : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                      }`}
                    >
                      {selectedTeamId === team.id && <Check className="h-3 w-3" />}
                      <Users className="h-3.5 w-3.5" />
                      {team.name}
                      <span className="text-xs opacity-60">({team.members.length})</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* User list */}
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  {selectedTeamId ? "Miembros del equipo" : "Todos los usuarios"}
                </p>

                <div className="flex flex-col gap-1 max-h-52 overflow-y-auto rounded-lg border border-border bg-background p-1">
                  {/* Unassign option */}
                  <button
                    type="button"
                    onClick={() => setSelectedUserId(null)}
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm text-left transition-colors ${
                      selectedUserId === null
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    <div className="h-7 w-7 rounded-full border border-border bg-muted flex items-center justify-center shrink-0">
                      <X className="h-3.5 w-3.5" />
                    </div>
                    <span>Sin asignar</span>
                    {selectedUserId === null && <Check className="h-4 w-4 ml-auto shrink-0" />}
                  </button>

                  {visibleUsers.length === 0 && (
                    <p className="px-3 py-4 text-xs text-muted-foreground text-center italic">
                      {selectedTeamId ? "Este equipo no tiene miembros" : "No hay usuarios disponibles"}
                    </p>
                  )}

                  {visibleUsers.map((u) => (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => setSelectedUserId(u.id)}
                      className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm text-left transition-colors ${
                        selectedUserId === u.id
                          ? "bg-primary/10 text-primary"
                          : "text-foreground hover:bg-muted"
                      }`}
                    >
                      <Avatar name={u.full_name} size="sm" />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{u.full_name}</p>
                        <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                      </div>
                      {selectedUserId === u.id && <Check className="h-4 w-4 ml-auto shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Error */}
              {error && (
                <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                  {error}
                </p>
              )}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-4">
            <Dialog.Close asChild>
              <button
                type="button"
                className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Cancelar
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={assign.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {assign.isPending ? <Spinner size="sm" /> : <UserCheck className="h-4 w-4" />}
              Asignar caso
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
