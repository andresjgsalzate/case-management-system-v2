"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Tag } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { SearchBar } from "@/components/molecules/SearchBar";
import { Spinner } from "@/components/atoms/Spinner";
import { truncate } from "@/lib/utils";
import type { Disposition, ApiResponse } from "@/lib/types";

function useDispositions(search?: string) {
  return useQuery({
    queryKey: ["dispositions", search],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Disposition[]>>("/dispositions", {
        params: search ? { q: search } : undefined,
      });
      return data.data ?? [];
    },
  });
}

export default function DispositionsPage() {
  const [search, setSearch] = useState("");
  const { data: dispositions = [], isLoading } = useDispositions(search || undefined);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Disposiciones</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Respuestas y plantillas predefinidas para casos
        </p>
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Buscar disposición…"
        className="max-w-sm"
      />

      {isLoading && (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      )}

      {!isLoading && dispositions.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
          <Tag className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No hay disposiciones</p>
        </div>
      )}

      <div className="grid gap-2">
        {dispositions.map((d) => (
          <div
            key={d.id}
            className="rounded-lg border border-border bg-card p-4 flex items-start gap-3 hover:border-primary/30 transition-colors"
          >
            <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
              <Tag className="h-4 w-4 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">{d.title}</p>
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                {truncate(d.content, 140)}
              </p>
              <p className="text-xs text-muted-foreground mt-1.5">
                Usada {d.usage_count} vece{d.usage_count !== 1 ? "s" : "z"}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
