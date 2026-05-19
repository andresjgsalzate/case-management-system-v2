// React Query hooks for the n8n workflow catalog.
import {
  useMutation, useQuery, useQueryClient,
} from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateN8nWorkflowPayload,
  N8nWorkflow,
  UpdateN8nWorkflowPayload,
} from "@/lib/types";

const BASE = "/n8n-workflows";

const keys = {
  all: ["n8n-workflows"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: ListFilters) => [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
};

export interface ListFilters {
  only_active?: boolean;
}

export function useN8nWorkflows(filters: ListFilters = {}) {
  return useQuery<N8nWorkflow[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.only_active) params.set("only_active", "true");
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<N8nWorkflow[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useN8nWorkflow(id: string | null | undefined) {
  return useQuery<N8nWorkflow>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<N8nWorkflow>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

export function useCreateN8nWorkflow() {
  const qc = useQueryClient();
  return useMutation<N8nWorkflow, Error, CreateN8nWorkflowPayload>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<ApiResponse<N8nWorkflow>>(
        BASE, body,
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

interface UpdateArgs {
  id: string;
  body: UpdateN8nWorkflowPayload;
}

export function useUpdateN8nWorkflow() {
  const qc = useQueryClient();
  return useMutation<N8nWorkflow, Error, UpdateArgs>({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.patch<ApiResponse<N8nWorkflow>>(
        `${BASE}/${id}`, body,
      );
      return data.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: keys.all });
      qc.invalidateQueries({ queryKey: keys.detail(vars.id) });
    },
  });
}

export function useDeleteN8nWorkflow() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(`${BASE}/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}
