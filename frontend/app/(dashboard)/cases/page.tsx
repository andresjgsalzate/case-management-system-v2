"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { SearchBar } from "@/components/molecules/SearchBar";
import { CaseTable } from "@/components/organisms/CaseTable";
import { useCases, useCasePriorities } from "@/hooks/useCases";
import type { Case } from "@/lib/types";

const STATUS_TABS = [
  { label: "Todos", value: "" },
  { label: "Abiertos", value: "open" },
  { label: "En progreso", value: "in_progress" },
  { label: "Pendientes", value: "pending" },
  { label: "Cerrados", value: "closed" },
];

const QUEUE_TABS: { label: string; value: "mine" | "team" | "all" }[] = [
  { label: "Mi cola", value: "mine" },
  { label: "Equipo", value: "team" },
  { label: "Todos", value: "all" },
];

export default function CasesPage() {
  const [search, setSearch] = useState("");
  const [activeStatus, setActiveStatus] = useState("");
  const [activePriority, setActivePriority] = useState("");
  const [queue, setQueue] = useState<"mine" | "team" | "all">("mine");

  const { data: cases = [], isLoading } = useCases({
    ...(activeStatus ? { status: activeStatus } : {}),
    queue,
  });
  const { data: priorities = [] } = useCasePriorities();

  const filtered: Case[] = cases.filter((c) => {
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!c.title.toLowerCase().includes(q) && !c.case_number.toLowerCase().includes(q)) return false;
    }
    if (activePriority && c.priority_id !== activePriority) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-5">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Casos</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isLoading ? "Cargando…" : `${filtered.length} caso${filtered.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Link href="/cases/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            Nuevo caso
          </Button>
        </Link>
      </div>

      {/* Queue tabs */}
      <div className="flex items-center gap-1 border-b border-border">
        {QUEUE_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setQueue(tab.value)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              queue === tab.value
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filters row */}
      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar por título o número…"
          className="sm:w-64"
        />

        {/* Status tabs */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveStatus(tab.value)}
              className={`px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition-colors ${
                activeStatus === tab.value
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Priority filter */}
        <select
          value={activePriority}
          onChange={(e) => setActivePriority(e.target.value)}
          className="h-8 rounded-md border border-border bg-background px-2 text-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Todas las prioridades</option>
          {priorities.map((p: { id: string; name: string }) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <CaseTable cases={filtered} isLoading={isLoading} />
      </div>
    </div>
  );
}
