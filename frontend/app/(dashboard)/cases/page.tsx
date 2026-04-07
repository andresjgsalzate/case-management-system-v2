"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/atoms/Button";
import { SearchBar } from "@/components/molecules/SearchBar";
import { CaseTable } from "@/components/organisms/CaseTable";
import { useCases } from "@/hooks/useCases";
import type { Case } from "@/lib/types";

const STATUS_TABS = [
  { label: "Todos", value: "" },
  { label: "Abiertos", value: "open" },
  { label: "En progreso", value: "in_progress" },
  { label: "Pendientes", value: "pending" },
  { label: "Cerrados", value: "closed" },
];

export default function CasesPage() {
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("");

  const { data: cases = [], isLoading } = useCases(
    activeTab ? { status: activeTab } : undefined
  );

  const filtered: Case[] = search.trim()
    ? cases.filter(
        (c) =>
          c.title.toLowerCase().includes(search.toLowerCase()) ||
          c.case_number.toLowerCase().includes(search.toLowerCase())
      )
    : cases;

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

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar por título o número…"
          className="sm:w-72"
        />
        <div className="flex items-center gap-1 overflow-x-auto">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={`px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition-colors duration-150 ${
                activeTab === tab.value
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <CaseTable cases={filtered} isLoading={isLoading} />
      </div>
    </div>
  );
}
