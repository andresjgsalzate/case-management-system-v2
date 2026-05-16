"use client";

import { X } from "lucide-react";

import { useInboundEventDetail } from "@/hooks/useInboundEvents";

interface Props {
  eventId: string | null;
  onClose: () => void;
}

export function InboundEventDetailModal({ eventId, onClose }: Props) {
  const { data, isLoading } = useInboundEventDetail(eventId);

  if (!eventId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">Detalle del evento entrante</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {isLoading ? (
          <p className="p-4 text-sm">Cargando…</p>
        ) : !data ? (
          <p className="p-4 text-sm">No encontrado.</p>
        ) : (
          <div className="space-y-4 p-4 text-sm">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <dt className="font-medium text-muted-foreground">ID</dt>
              <dd className="font-mono">{data.id}</dd>
              <dt className="font-medium text-muted-foreground">Estado</dt>
              <dd>{data.status}</dd>
              <dt className="font-medium text-muted-foreground">Fuente</dt>
              <dd className="font-mono">{data.source_id}</dd>
              <dt className="font-medium text-muted-foreground">Caso vinculado</dt>
              <dd className="font-mono">{data.case_id ?? "—"}</dd>
              <dt className="font-medium text-muted-foreground">Intentos</dt>
              <dd>{data.attempt_count} / {data.max_attempts}</dd>
              <dt className="font-medium text-muted-foreground">Recibido</dt>
              <dd>{new Date(data.received_at).toLocaleString()}</dd>
              <dt className="font-medium text-muted-foreground">Procesado</dt>
              <dd>
                {data.processed_at
                  ? new Date(data.processed_at).toLocaleString()
                  : "—"}
              </dd>
              <dt className="font-medium text-muted-foreground">Próximo retry</dt>
              <dd>
                {data.next_retry_at
                  ? new Date(data.next_retry_at).toLocaleString()
                  : "—"}
              </dd>
              <dt className="font-medium text-muted-foreground">Idempotency key</dt>
              <dd className="col-span-1 break-all font-mono text-[10px]">
                {data.idempotency_key}
              </dd>
            </dl>

            {data.last_error ? (
              <section>
                <h3 className="mb-1 text-sm font-semibold text-red-700">
                  Último error
                </h3>
                <pre className="overflow-auto rounded bg-red-50 p-2 text-xs text-red-900">
                  {data.last_error}
                </pre>
              </section>
            ) : null}

            <section>
              <h3 className="mb-1 text-sm font-semibold">Payload original</h3>
              <pre className="max-h-96 overflow-auto rounded bg-muted/40 p-2 text-xs">
                {JSON.stringify(data.raw_payload, null, 2)}
              </pre>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
