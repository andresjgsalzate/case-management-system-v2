// CRUD hooks for the triage catalog admin UI (/settings/triage-catalogs).
// Read hooks support include_inactive so the admin can see + re-enable
// disabled rows. Mutations invalidate both the admin list AND the
// read-only lists consumed by the triage form (useTriageCatalogs).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateSlaPolicyPayload,
  CreateToolActionPayload,
  CreateToolTypePayload,
  TriageSlaPolicy,
  TriageToolAction,
  TriageToolType,
  UpdateSlaPolicyPayload,
  UpdateToolActionPayload,
  UpdateToolTypePayload,
} from "@/lib/types";

const BASE = "/triage-catalogs";

// Invalidate every triage-catalog query (admin + form dropdowns).
function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["triage-tool-types"] });
  qc.invalidateQueries({ queryKey: ["triage-tool-actions"] });
  qc.invalidateQueries({ queryKey: ["triage-sla-policies"] });
  qc.invalidateQueries({ queryKey: ["triage-catalogs-admin"] });
}

// ─── Tool types ─────────────────────────────────────────────────

export function useToolTypesAdmin() {
  return useQuery<TriageToolType[]>({
    queryKey: ["triage-catalogs-admin", "tool-types"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<TriageToolType[]>>(
        `${BASE}/tool-types?include_inactive=true`,
      );
      return data.data;
    },
  });
}

export function useCreateToolType() {
  const qc = useQueryClient();
  return useMutation<TriageToolType, Error, CreateToolTypePayload>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<ApiResponse<TriageToolType>>(
        `${BASE}/tool-types`, body,
      );
      return data.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateToolType() {
  const qc = useQueryClient();
  return useMutation<
    TriageToolType, Error, { id: string; body: UpdateToolTypePayload }
  >({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.put<ApiResponse<TriageToolType>>(
        `${BASE}/tool-types/${id}`, body,
      );
      return data.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteToolType() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(`${BASE}/tool-types/${id}`);
    },
    onSuccess: () => invalidateAll(qc),
  });
}

// ─── Tool actions ───────────────────────────────────────────────

export function useToolActionsAdmin() {
  return useQuery<TriageToolAction[]>({
    queryKey: ["triage-catalogs-admin", "tool-actions"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<TriageToolAction[]>>(
        `${BASE}/tool-actions?include_inactive=true`,
      );
      return data.data;
    },
  });
}

export function useCreateToolAction() {
  const qc = useQueryClient();
  return useMutation<TriageToolAction, Error, CreateToolActionPayload>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<ApiResponse<TriageToolAction>>(
        `${BASE}/tool-actions`, body,
      );
      return data.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateToolAction() {
  const qc = useQueryClient();
  return useMutation<
    TriageToolAction, Error, { id: string; body: UpdateToolActionPayload }
  >({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.put<ApiResponse<TriageToolAction>>(
        `${BASE}/tool-actions/${id}`, body,
      );
      return data.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteToolAction() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(`${BASE}/tool-actions/${id}`);
    },
    onSuccess: () => invalidateAll(qc),
  });
}

// ─── SLA policies ───────────────────────────────────────────────

export function useSlaPoliciesAdmin() {
  return useQuery<TriageSlaPolicy[]>({
    queryKey: ["triage-sla-policies"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<TriageSlaPolicy[]>>(
        `${BASE}/sla-policies`,
      );
      return data.data;
    },
  });
}

export function useCreateSlaPolicy() {
  const qc = useQueryClient();
  return useMutation<TriageSlaPolicy, Error, CreateSlaPolicyPayload>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<ApiResponse<TriageSlaPolicy>>(
        `${BASE}/sla-policies`, body,
      );
      return data.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useUpdateSlaPolicy() {
  const qc = useQueryClient();
  return useMutation<
    TriageSlaPolicy, Error, { id: string; body: UpdateSlaPolicyPayload }
  >({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.put<ApiResponse<TriageSlaPolicy>>(
        `${BASE}/sla-policies/${id}`, body,
      );
      return data.data;
    },
    onSuccess: () => invalidateAll(qc),
  });
}

export function useDeleteSlaPolicy() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(`${BASE}/sla-policies/${id}`);
    },
    onSuccess: () => invalidateAll(qc),
  });
}
