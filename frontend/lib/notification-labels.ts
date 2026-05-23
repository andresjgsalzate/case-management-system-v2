// Human-readable labels for taxonomy notification slugs. Slugs mirror
// the backend CHECK constraint (taxonomy_notifications.notify_phase /
// notify_channel). Shared by the editor (CRUD) and the detail panel
// (read-only view) so labels stay consistent.
import type { NotifyChannel, NotifyPhase } from "@/lib/types";

export const NOTIFY_PHASES: ReadonlyArray<readonly [NotifyPhase, string]> = [
  ["triage", "Triage"],
  ["created", "Creado"],
  ["critical_priority", "Prioridad crítica"],
  ["sla_breach", "SLA vencido"],
  ["resolved", "Resuelto"],
  ["promoted", "Promovido"],
];

export const NOTIFY_CHANNELS: ReadonlyArray<readonly [NotifyChannel, string]> = [
  ["email", "Email"],
  ["chat", "Chat"],
  ["sms", "SMS"],
  ["all", "Todos"],
];

const PHASE_MAP = new Map<string, string>(NOTIFY_PHASES);
const CHANNEL_MAP = new Map<string, string>(NOTIFY_CHANNELS);

export function phaseLabel(slug: string): string {
  return PHASE_MAP.get(slug) ?? slug;
}

export function channelLabel(slug: string): string {
  return CHANNEL_MAP.get(slug) ?? slug;
}
