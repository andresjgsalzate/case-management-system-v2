"use client";

import { Copy, Plus } from "lucide-react";
import { useState } from "react";

import { InboundEventDetailModal } from "@/components/organisms/InboundEventDetailModal";
import { InboundEventsTable } from "@/components/organisms/InboundEventsTable";
import { IntegrationSourceCreateModal } from "@/components/organisms/IntegrationSourceCreateModal";
import { IntegrationSourcesTable } from "@/components/organisms/IntegrationSourcesTable";
import { N8nWorkflowFormModal } from "@/components/organisms/N8nWorkflowFormModal";
import { N8nWorkflowsTable } from "@/components/organisms/N8nWorkflowsTable";
import type { InboundEvent, N8nWorkflow, RotateSecretResponse } from "@/lib/types";

type Tab = "sources" | "events" | "workflows";

export default function IntegrationsSettingsPage() {
  const [tab, setTab] = useState<Tab>("sources");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<InboundEvent | null>(null);
  const [rotated, setRotated] = useState<
    { secret: RotateSecretResponse; name: string } | null
  >(null);
  const [workflowModalOpen, setWorkflowModalOpen] = useState(false);
  const [editingWorkflow, setEditingWorkflow] = useState<N8nWorkflow | null>(null);

  function openCreateWorkflow() {
    setEditingWorkflow(null);
    setWorkflowModalOpen(true);
  }

  function openEditWorkflow(wf: N8nWorkflow) {
    setEditingWorkflow(wf);
    setWorkflowModalOpen(true);
  }

  return (
    <div className="space-y-4 p-4">
      <header>
        <h1 className="text-xl font-semibold">Integraciones</h1>
        <p className="text-sm text-muted-foreground">
          Fuentes de eventos (Wazuh, Splunk, …), bandeja de eventos entrantes y catálogo de workflows n8n.
        </p>
      </header>

      <nav className="flex gap-1 border-b">
        <TabButton active={tab === "sources"} onClick={() => setTab("sources")}>
          Fuentes
        </TabButton>
        <TabButton active={tab === "events"} onClick={() => setTab("events")}>
          Eventos entrantes
        </TabButton>
        <TabButton active={tab === "workflows"} onClick={() => setTab("workflows")}>
          Workflows n8n
        </TabButton>
      </nav>

      {tab === "sources" && (
        <section className="rounded border bg-card">
          <header className="flex items-center justify-between border-b px-3 py-2">
            <h2 className="text-sm font-semibold">Fuentes configuradas</h2>
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              <Plus className="h-3.5 w-3.5" /> Nueva fuente
            </button>
          </header>
          <IntegrationSourcesTable
            onSecretRevealed={(secret, name) =>
              setRotated({ secret, name })
            }
          />
        </section>
      )}

      {tab === "events" && (
        <section className="rounded border bg-card">
          <InboundEventsTable onSelect={(e) => setSelectedEvent(e)} />
        </section>
      )}

      {tab === "workflows" && (
        <section className="rounded border bg-card">
          <header className="flex items-center justify-between border-b px-3 py-2">
            <h2 className="text-sm font-semibold">Catálogo de workflows n8n</h2>
            <button
              type="button"
              onClick={openCreateWorkflow}
              className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              <Plus className="h-3.5 w-3.5" /> Nuevo workflow
            </button>
          </header>
          <N8nWorkflowsTable onEdit={openEditWorkflow} />
        </section>
      )}

      <IntegrationSourceCreateModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
      />

      <InboundEventDetailModal
        eventId={selectedEvent?.id ?? null}
        onClose={() => setSelectedEvent(null)}
      />

      <N8nWorkflowFormModal
        isOpen={workflowModalOpen}
        initial={editingWorkflow}
        onClose={() => setWorkflowModalOpen(false)}
      />

      {rotated ? (
        <RotatedSecretModal
          secret={rotated.secret.plaintext_secret}
          sourceName={rotated.name}
          onClose={() => setRotated(null)}
        />
      ) : null}
    </div>
  );
}

function TabButton({
  active, children, onClick,
}: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border-b-2 px-3 py-2 text-sm transition-colors ${
        active
          ? "border-blue-600 font-medium text-blue-700"
          : "border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function RotatedSecretModal({
  secret, sourceName, onClose,
}: { secret: string; sourceName: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-lg bg-card p-4 shadow-xl">
        <h2 className="mb-2 text-base font-semibold">
          Secreto rotado para &quot;{sourceName}&quot;
        </h2>
        <p className="mb-3 rounded bg-amber-50 px-3 py-2 text-sm text-amber-900">
          El secreto antiguo dejó de funcionar inmediatamente. Guarda el nuevo
          <strong> ahora</strong> — no se mostrará otra vez.
        </p>
        <div className="flex items-stretch gap-1">
          <input
            type="text"
            readOnly
            value={secret}
            className="flex-1 rounded border bg-muted/30 px-2 py-1 font-mono text-sm"
          />
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(secret)}
            className="rounded border px-2 hover:bg-muted"
            title="Copiar"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        </div>
        <footer className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            Listo
          </button>
        </footer>
      </div>
    </div>
  );
}
