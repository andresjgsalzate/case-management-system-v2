"use client";

import { useState } from "react";

import { apiClient } from "@/lib/apiClient";
import type {
  AlertReportIntegrityCheck,
  ApiResponse,
} from "@/lib/types";

interface Props {
  reportId: string;
}

export function IntegrityCheckBadge({ reportId }: Props) {
  const [result, setResult] = useState<AlertReportIntegrityCheck | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function verify() {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<
        ApiResponse<AlertReportIntegrityCheck>
      >(`/alert-reports/${reportId}/verify`);
      setResult(data.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "error");
    } finally {
      setLoading(false);
    }
  }

  if (error) {
    return (
      <span className="text-xs text-red-600" role="alert">
        Error: {error}
      </span>
    );
  }

  if (!result) {
    return (
      <button
        type="button"
        onClick={verify}
        disabled={loading}
        className="text-xs text-blue-600 underline disabled:opacity-50"
      >
        {loading ? "Verificando..." : "Verificar integridad"}
      </button>
    );
  }

  if (result.is_intact) {
    return (
      <span
        className="text-xs text-green-600 font-medium"
        title={`SHA-256: ${result.expected_sha256}`}
      >
        ✓ Íntegro
      </span>
    );
  }
  return (
    <span
      className="text-xs text-red-600 font-medium"
      role="alert"
      title={`expected ${result.expected_sha256} got ${result.actual_sha256}`}
    >
      ✗ Alterado
    </span>
  );
}
