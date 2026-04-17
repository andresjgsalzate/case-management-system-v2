import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format ISO date string to locale date */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Format ISO date string to relative time ("hace 3h") */
export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "ahora";
  if (mins < 60) return `hace ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `hace ${days}d`;
  return formatDate(iso);
}

/** Truncate text to maxLength with ellipsis */
export function truncate(text: string, maxLength: number): string {
  return text.length > maxLength ? text.slice(0, maxLength) + "…" : text;
}

/** Get initials from a full name */
export function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

// ── Solution structured data ───────────────────────────────────────────────────

export interface SolutionData {
  summary: string;       // Resumen de la solución
  root_cause: string;    // Causa raíz del problema
  steps: string;         // Pasos aplicados para resolver
  prevention?: string;   // Cómo prevenir en el futuro (opcional)
  kb_notes?: string;     // Notas para base de conocimiento / IA (opcional)
}

/** Serialize SolutionData to a JSON string for storage */
export function serializeSolution(data: SolutionData): string {
  return JSON.stringify(data);
}

/** Parse a solution string: returns structured data if JSON, or legacy plain text wrapped in summary */
export function parseSolution(raw: string | null | undefined): SolutionData | null {
  if (!raw?.trim()) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.summary === "string") return parsed as SolutionData;
  } catch {
    // Legacy plain text — wrap it in summary field for display
    return { summary: raw, root_cause: "", steps: "" };
  }
  return null;
}
