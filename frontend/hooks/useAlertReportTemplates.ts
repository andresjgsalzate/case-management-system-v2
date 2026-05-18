// Frontend hooks for Sub-spec 08 — Alert Report templates CRUD.
import {
  useMutation, useQuery, useQueryClient,
} from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  AlertReportTemplate,
  AlertReportTemplateCreate,
  AlertReportTemplateUpdate,
  ApiResponse,
} from "@/lib/types";

const BASE = "/alert-report-templates";

const keys = {
  all: ["alert-report-templates"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: ListFilters) => [...keys.lists(), filters] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
};

export interface ListFilters {
  include_inactive?: boolean;
}

export function useAlertReportTemplates(filters: ListFilters = {}) {
  return useQuery<AlertReportTemplate[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.include_inactive) params.set("include_inactive", "true");
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<AlertReportTemplate[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useAlertReportTemplate(
  id: string | null | undefined,
) {
  return useQuery<AlertReportTemplate>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AlertReportTemplate>>(
        `${BASE}/${id}`,
      );
      return data.data;
    },
  });
}

export function useCreateAlertReportTemplate() {
  const queryClient = useQueryClient();
  return useMutation<AlertReportTemplate, Error, AlertReportTemplateCreate>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<ApiResponse<AlertReportTemplate>>(
        BASE, body,
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

interface UpdateInput {
  id: string;
  body: AlertReportTemplateUpdate;
}

export function useUpdateAlertReportTemplate() {
  const queryClient = useQueryClient();
  return useMutation<AlertReportTemplate, Error, UpdateInput>({
    mutationFn: async ({ id, body }) => {
      const { data } = await apiClient.patch<ApiResponse<AlertReportTemplate>>(
        `${BASE}/${id}`, body,
      );
      return data.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: keys.all });
      queryClient.invalidateQueries({
        queryKey: keys.detail(variables.id),
      });
    },
  });
}

export function useDeleteAlertReportTemplate() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await apiClient.delete(`${BASE}/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useSetDefaultTemplate() {
  const queryClient = useQueryClient();
  return useMutation<AlertReportTemplate, Error, string>({
    mutationFn: async (id) => {
      const { data } = await apiClient.post<ApiResponse<AlertReportTemplate>>(
        `${BASE}/${id}/set-default`,
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.all });
    },
  });
}
