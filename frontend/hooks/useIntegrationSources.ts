// Frontend hooks for Sub-spec 04 — Integration Sources CRUD + secret rotation.
// Pattern mirrors useSecurityTaxonomies.ts.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateIntegrationSourcePayload,
  CreateSourceResponse,
  IntegrationSource,
  RotateSecretResponse,
  UpdateIntegrationSourcePayload,
} from "@/lib/types";

const BASE = "/integration-sources";

const keys = {
  all: ["integration-sources"] as const,
  lists: () => [...keys.all, "list"] as const,
};

// ── Reads ────────────────────────────────────────────────────────────────────

export function useIntegrationSources() {
  return useQuery<IntegrationSource[]>({
    queryKey: keys.lists(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<IntegrationSource[]>>(BASE);
      return data.data;
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useCreateIntegrationSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateIntegrationSourcePayload) => {
      const { data } = await apiClient.post<ApiResponse<CreateSourceResponse>>(
        BASE,
        payload,
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useUpdateIntegrationSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id, payload,
    }: { id: string; payload: UpdateIntegrationSourcePayload }) => {
      const { data } = await apiClient.patch<ApiResponse<IntegrationSource>>(
        `${BASE}/${id}`,
        payload,
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useRotateSourceSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<ApiResponse<RotateSecretResponse>>(
        `${BASE}/${id}/rotate-secret`,
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useSoftDeleteIntegrationSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.delete<ApiResponse<unknown>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}
