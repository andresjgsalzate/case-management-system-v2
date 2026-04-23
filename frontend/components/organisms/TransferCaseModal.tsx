"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useTransferCase } from "@/hooks/useTransferCase";
import { apiClient } from "@/lib/apiClient";
import { Button } from "@/components/atoms/Button";
import { Spinner } from "@/components/atoms/Spinner";
import type { ApiResponse, Team } from "@/lib/types";

interface TeamWithMembers extends Team {
  members?: TeamMember[];
}

interface TeamMember {
  user_id: string;
  full_name: string | null;
  email: string | null;
  team_role: string;
}

interface TransferCaseModalProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function TransferCaseModal({ caseId, open, onClose, onSuccess }: TransferCaseModalProps) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [teamId, setTeamId] = useState("");
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const transfer = useTransferCase(caseId);

  useEffect(() => {
    if (!open) return;
    setError("");
    setReason("");
    setTeamId("");
    setUserId("");
    (async () => {
      setLoading(true);
      try {
        const { data } = await apiClient.get<ApiResponse<Team[]>>("/teams");
        setTeams(data.data ?? []);
      } finally {
        setLoading(false);
      }
    })();
  }, [open]);

  useEffect(() => {
    if (!teamId) {
      setMembers([]);
      setUserId("");
      return;
    }
    (async () => {
      const { data } = await apiClient.get<ApiResponse<TeamWithMembers>>(
        `/teams/${teamId}`
      );
      setMembers(data.data?.members ?? []);
    })();
  }, [teamId]);

  async function handleConfirm() {
    setError("");
    if (!userId || !reason.trim()) {
      setError("Selecciona un usuario y escribe un motivo.");
      return;
    }
    try {
      await transfer.mutateAsync({ to_user_id: userId, reason: reason.trim() });
      onSuccess?.();
      onClose();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "No se pudo transferir el caso.");
    }
  }

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-card rounded-lg border border-border p-6 w-full max-w-md shadow-xl flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Transferir caso</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {loading && <Spinner size="sm" />}

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Equipo destino</label>
          <select
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            className="px-3 py-2 text-sm rounded-md border border-border bg-background"
          >
            <option value="">Selecciona…</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Usuario destino</label>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            disabled={!teamId}
            className="px-3 py-2 text-sm rounded-md border border-border bg-background disabled:opacity-50"
          >
            <option value="">Selecciona…</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name ?? m.email ?? m.user_id}
                {m.team_role ? ` — ${m.team_role}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Motivo (obligatorio)</label>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explica por qué estás transfiriendo el caso…"
            className="px-3 py-2 text-sm rounded-md border border-border bg-background resize-none"
          />
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button
            onClick={handleConfirm}
            loading={transfer.isPending}
            disabled={!userId || !reason.trim()}
          >
            Confirmar transferencia
          </Button>
        </div>
      </div>
    </div>
  );
}
