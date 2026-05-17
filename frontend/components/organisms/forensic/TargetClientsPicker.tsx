"use client";

import { useState } from "react";

import { useVeloClients } from "@/hooks/useVeloClients";

type Mode = "single" | "multi" | "all";

interface Props {
  selected: string[];
  onChange: (clients: string[]) => void;
}

export function TargetClientsPicker({ selected, onChange }: Props) {
  const [mode, setMode] = useState<Mode>("single");
  const [search, setSearch] = useState("");
  const { data: clients = [], isLoading } = useVeloClients(search);

  function pickMode(next: Mode) {
    setMode(next);
    onChange(next === "all" ? ["*"] : []);
  }

  function toggleClient(clientId: string) {
    if (mode === "single") {
      onChange([clientId]);
      return;
    }
    onChange(
      selected.includes(clientId)
        ? selected.filter((c) => c !== clientId)
        : [...selected, clientId],
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1">
          <input
            type="radio"
            name="target-mode"
            checked={mode === "single"}
            onChange={() => pickMode("single")}
          />
          Host único
        </label>
        <label className="flex items-center gap-1">
          <input
            type="radio"
            name="target-mode"
            checked={mode === "multi"}
            onChange={() => pickMode("multi")}
          />
          Múltiples hosts
        </label>
        <label className="flex items-center gap-1">
          <input
            type="radio"
            name="target-mode"
            checked={mode === "all"}
            onChange={() => pickMode("all")}
          />
          Toda la organización
        </label>
      </div>

      {mode !== "all" && (
        <>
          <input
            type="text"
            placeholder="Buscar por hostname..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border rounded px-2 py-1 text-sm"
          />
          <ul className="max-h-48 overflow-y-auto border rounded">
            {isLoading && (
              <li className="p-2 text-sm text-gray-500">Cargando hosts...</li>
            )}
            {!isLoading && clients.length === 0 && (
              <li className="p-2 text-sm text-gray-500">
                No hay hosts visibles para este tenant.
              </li>
            )}
            {clients.map((c) => (
              <li
                key={c.client_id}
                className={`p-2 cursor-pointer text-sm ${
                  selected.includes(c.client_id) ? "bg-blue-50" : ""
                }`}
                onClick={() => toggleClient(c.client_id)}
              >
                <div className="font-mono">{c.hostname || c.client_id}</div>
                {c.os && (
                  <div className="text-xs text-gray-500">{c.os}</div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {selected.length > 0 && mode !== "all" && (
        <div className="text-xs text-gray-600">
          {selected.length} host{selected.length > 1 ? "s" : ""} seleccionado
          {selected.length > 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
