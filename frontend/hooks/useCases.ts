import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { Case, ApiResponse } from "@/lib/types";

const CASES_KEY = "cases";

export function useCases(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [CASES_KEY, params],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Case[]>>("/cases", { params });
      return data.data ?? [];
    },
  });
}

export function useCase(id: string) {
  return useQuery({
    queryKey: [CASES_KEY, id],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<Case>>(`/cases/${id}`);
      return data.data;
    },
    enabled: !!id,
  });
}

export function useCreateCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      title: string;
      description?: string;
      priority_id: string;
      application_id?: string;
    }) => {
      const { data } = await apiClient.post<ApiResponse<Case>>("/cases", payload);
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [CASES_KEY] }),
  });
}

export function useUpdateCase(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Case>) => {
      const { data } = await apiClient.patch<ApiResponse<Case>>(`/cases/${id}`, payload);
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [CASES_KEY, id] });
      qc.invalidateQueries({ queryKey: [CASES_KEY] });
    },
  });
}

export function useCaseStatuses() {
  return useQuery({
    queryKey: ["case-statuses"],
    queryFn: async () => {
      const { data } = await apiClient.get("/case-statuses");
      return data.data ?? [];
    },
    staleTime: 5 * 60_000,
  });
}

export function useCasePriorities() {
  return useQuery({
    queryKey: ["case-priorities"],
    queryFn: async () => {
      const { data } = await apiClient.get("/case-priorities");
      return data.data ?? [];
    },
    staleTime: 5 * 60_000,
  });
}

export function useApplications() {
  return useQuery({
    queryKey: ["applications"],
    queryFn: async () => {
      const { data } = await apiClient.get("/applications");
      return data.data ?? [];
    },
    staleTime: 5 * 60_000,
  });
}
