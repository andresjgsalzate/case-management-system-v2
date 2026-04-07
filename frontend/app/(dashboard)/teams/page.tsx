"use client";

import { Users, User } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";
import type { Team, ApiResponse } from "@/lib/types";

function useTeams() {
  return useQuery({
    queryKey: ["teams"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Team[]>>("/teams");
      return data.data ?? [];
    },
  });
}

export default function TeamsPage() {
  const { data: teams = [], isLoading } = useTeams();

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Equipos</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {isLoading ? "Cargando…" : `${teams.length} equipo${teams.length !== 1 ? "s" : ""}`}
        </p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!isLoading && teams.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
          <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No hay equipos configurados</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {teams.map((team) => (
          <div
            key={team.id}
            className="rounded-lg border border-border bg-card p-4 hover:shadow-sm transition-shadow"
          >
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                <Users className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-foreground truncate">{team.name}</h3>
                {team.description && (
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                    {team.description}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <User className="h-3.5 w-3.5" />
                {team.member_count ?? 0} miembro{(team.member_count ?? 0) !== 1 ? "s" : ""}
              </span>
              <span>Creado {formatDate(team.created_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
