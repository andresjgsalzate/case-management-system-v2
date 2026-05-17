"use client";

import { useState } from "react";

import { useForensicArtifacts } from "@/hooks/useForensicArtifacts";
import type { ForensicArtifact } from "@/lib/types";

interface Props {
  selectedArtifactId: string | null;
  onSelect: (artifact: ForensicArtifact) => void;
}

const CATEGORIES = [
  { value: "", label: "Todas las categorías" },
  { value: "detection", label: "Detección" },
  { value: "collection", label: "Recolección" },
  { value: "remediation", label: "Remediación" },
  { value: "live_response", label: "Live Response" },
  { value: "triage", label: "Triage" },
  { value: "persistence", label: "Persistencia" },
];

export function ArtifactPicker({ selectedArtifactId, onSelect }: Props) {
  const [featuredOnly, setFeaturedOnly] = useState(true);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");

  const { data: artifacts = [], isLoading } = useForensicArtifacts({
    featured_only: featuredOnly,
    category: category || undefined,
    search: search || undefined,
    include_destructive: true,
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setFeaturedOnly(!featuredOnly)}
          className={`px-3 py-1 rounded text-sm ${
            featuredOnly
              ? "bg-yellow-100 border border-yellow-400"
              : "border"
          }`}
        >
          ⭐ Featured
        </button>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="border rounded px-2 py-1 text-sm"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="🔍 Buscar..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border rounded px-2 py-1 text-sm flex-1"
        />
      </div>

      {isLoading && (
        <div className="text-sm text-gray-500">Cargando artifacts...</div>
      )}

      <ul className="space-y-1 max-h-72 overflow-y-auto">
        {artifacts.map((a) => {
          const disabled = a.is_destructive;
          return (
            <li
              key={a.id}
              className={`p-2 rounded border cursor-pointer ${
                selectedArtifactId === a.id
                  ? "border-blue-500 bg-blue-50"
                  : ""
              } ${disabled ? "opacity-60 cursor-not-allowed" : ""}`}
              onClick={() => !disabled && onSelect(a)}
            >
              <div className="flex items-center gap-2">
                {a.is_featured && <span aria-label="featured">⭐</span>}
                {a.is_destructive && (
                  <span aria-label="destructive" title="Destructivo">
                    🔒
                  </span>
                )}
                <span className="font-mono text-sm">{a.name}</span>
              </div>
              {a.description && (
                <div className="text-xs text-gray-600 mt-0.5">
                  {a.description}
                </div>
              )}
              {a.is_destructive && (
                <div className="text-xs text-red-600 mt-1">
                  Destructivo — solo via workflow n8n con aprobación
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
