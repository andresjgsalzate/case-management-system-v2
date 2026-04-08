"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { UserPlus, CheckCircle, XCircle, Mail } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { Avatar } from "@/components/atoms/Avatar";
import { Badge } from "@/components/atoms/Badge";
import { Spinner } from "@/components/atoms/Spinner";
import { SearchBar } from "@/components/molecules/SearchBar";
import { formatDate } from "@/lib/utils";
import type { User, ApiResponse } from "@/lib/types";

function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<User[]>>("/users");
      return data.data ?? [];
    },
  });
}

export default function UsersSettingsPage() {
  const [search, setSearch] = useState("");
  const { data: users = [], isLoading } = useUsers();

  const filtered = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Usuarios</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${users.length} usuario${users.length !== 1 ? "s" : ""} en el sistema`}
          </p>
        </div>
        <button
          type="button"
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <UserPlus className="h-4 w-4" />
          Nuevo usuario
        </button>
      </div>

      <SearchBar value={search} onChange={setSearch} placeholder="Buscar por nombre o email…" className="max-w-sm" />

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {!isLoading && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                {["Usuario", "Email", "Estado", "Creado"].map((col) => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-sm text-muted-foreground">
                    No hay usuarios que coincidan
                  </td>
                </tr>
              ) : (
                filtered.map((user) => (
                  <tr key={user.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar name={user.full_name} size="sm" />
                        <span className="font-medium text-foreground">{user.full_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <Mail className="h-3.5 w-3.5" />
                        {user.email}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {user.is_active ? (
                        <Badge variant="success" className="flex items-center gap-1 w-fit">
                          <CheckCircle className="h-3 w-3" />
                          Activo
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="flex items-center gap-1 w-fit text-muted-foreground">
                          <XCircle className="h-3 w-3" />
                          Inactivo
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(user.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
