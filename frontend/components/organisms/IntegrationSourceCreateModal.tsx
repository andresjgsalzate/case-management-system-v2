"use client";

import { Copy, X } from "lucide-react";
import { useState } from "react";

import { useCreateIntegrationSource } from "@/hooks/useIntegrationSources";
import type {
  AuthMethod,
  CreateSourceResponse,
  SourceType,
} from "@/lib/types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const SOURCE_TYPES: SourceType[] = [
  "wazuh", "splunk", "sentinel", "crowdstrike",
  "qradar", "wazuh_velociraptor", "n8n", "custom",
];

const AUTH_METHODS: AuthMethod[] = ["hmac", "api_key", "bearer", "none"];

export function IntegrationSourceCreateModal({ isOpen, onClose }: Props) {
  const create = useCreateIntegrationSource();
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("wazuh");
  const [authMethod, setAuthMethod] = useState<AuthMethod>("hmac");
  const [rateLimit, setRateLimit] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<CreateSourceResponse | null>(null);

  function reset() {
    setName("");
    setSourceType("wazuh");
    setAuthMethod("hmac");
    setRateLimit("");
    setErrorMsg(null);
    setRevealed(null);
  }

  function close() {
    reset();
    onClose();
  }

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    if (!name.trim()) {
      setErrorMsg("El nombre es requerido");
      return;
    }
    try {
      const result = await create.mutateAsync({
        tenant_id: null,
        name: name.trim(),
        source_type: sourceType,
        auth_method: authMethod,
        rate_limit_per_minute: rateLimit ? Number(rateLimit) : null,
      });
      setRevealed(result);
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Error al crear fuente",
      );
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-card shadow-xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-base font-semibold">
            {revealed ? "Fuente creada" : "Nueva fuente de integración"}
          </h2>
          <button
            type="button"
            onClick={close}
            className="rounded p-1 hover:bg-muted"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {revealed ? (
          <SecretReveal data={revealed} onDone={close} />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 p-4">
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Nombre *</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ej: Wazuh Prod"
                className="w-full rounded border px-2 py-1 text-sm"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Tipo de fuente</span>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value as SourceType)}
                  className="w-full rounded border px-2 py-1 text-sm"
                >
                  {SOURCE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Método de autenticación</span>
                <select
                  value={authMethod}
                  onChange={(e) => setAuthMethod(e.target.value as AuthMethod)}
                  className="w-full rounded border px-2 py-1 text-sm"
                >
                  {AUTH_METHODS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">
                Rate limit (por minuto, opcional)
              </span>
              <input
                type="number"
                min="0"
                value={rateLimit}
                onChange={(e) => setRateLimit(e.target.value)}
                placeholder="Dejar vacío para sin límite"
                className="w-full rounded border px-2 py-1 text-sm font-mono"
              />
            </label>

            {errorMsg ? (
              <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
                {errorMsg}
              </p>
            ) : null}

            <footer className="flex justify-end gap-2 border-t pt-3">
              <button
                type="button"
                onClick={close}
                className="rounded border px-3 py-1.5 text-sm hover:bg-muted"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={create.isPending}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {create.isPending ? "Creando…" : "Crear fuente"}
              </button>
            </footer>
          </form>
        )}
      </div>
    </div>
  );
}

function SecretReveal({
  data,
  onDone,
}: { data: CreateSourceResponse; onDone: () => void }) {
  return (
    <div className="space-y-3 p-4 text-sm">
      <p className="rounded bg-amber-50 px-3 py-2 text-amber-900">
        Guarda esta información ahora. <strong>El secreto no se mostrará otra vez.</strong>
      </p>
      <CopyField
        label="URL del webhook (configurar en la herramienta upstream)"
        value={data.webhook_url ?? ""}
      />
      <CopyField label="Secreto (plaintext)" value={data.plaintext_secret} mono />
      <CopyField
        label="Header esperado"
        value={data.source.auth_header_name ?? "X-CMS-Signature"}
      />
      <footer className="flex justify-end border-t pt-3">
        <button
          type="button"
          onClick={onDone}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Listo
        </button>
      </footer>
    </div>
  );
}

function CopyField({
  label, value, mono,
}: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex items-stretch gap-1">
        <input
          type="text"
          readOnly
          value={value}
          className={`flex-1 rounded border bg-muted/30 px-2 py-1 text-sm ${mono ? "font-mono" : ""}`}
        />
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(value)}
          className="rounded border px-2 hover:bg-muted"
          title="Copiar al portapapeles"
        >
          <Copy className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
