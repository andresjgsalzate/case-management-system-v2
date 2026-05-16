// Frontend hooks for Sub-spec 02 — Security Taxonomies.
// Pattern follows useEmailConfig.ts: @tanstack/react-query + apiClient + ApiResponse<T>.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateCatalogMappingPayload,
  CreateNotificationPayload,
  CreateTaxonomyPayload,
  SecurityTaxonomy,
  SecurityTaxonomyTreeNode,
  TaxonomyAuditLogEntry,
  TaxonomyCatalogMapping,
  TaxonomyChangeType,
  TaxonomyNotification,
  UpdateTaxonomyPayload,
} from "@/lib/types";

const BASE = "/security-taxonomies";

// ── Query keys (single source of truth for cache invalidation) ───────────────

const keys = {
  all: ["security-taxonomies"] as const,
  lists: () => [...keys.all, "list"] as const,
  list: (filters: TaxonomyListFilters) => [...keys.lists(), filters] as const,
  tree: () => [...keys.all, "tree"] as const,
  detail: (id: string) => [...keys.all, "detail", id] as const,
  audit: (id: string, changeType?: TaxonomyChangeType) =>
    [...keys.all, "audit", id, changeType ?? "all"] as const,
};

export interface TaxonomyListFilters {
  parent_id?: string;
  search?: string;
  include_inactive?: boolean;
}

// ── Reads ────────────────────────────────────────────────────────────────────

export function useSecurityTaxonomies(filters: TaxonomyListFilters = {}) {
  return useQuery<SecurityTaxonomy[]>({
    queryKey: keys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.parent_id) params.set("parent_id", filters.parent_id);
      if (filters.search) params.set("search", filters.search);
      if (filters.include_inactive) params.set("include_inactive", "true");
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<SecurityTaxonomy[]>>(
        `${BASE}${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useTaxonomyTree(includeInactive = false) {
  return useQuery<SecurityTaxonomyTreeNode[]>({
    queryKey: keys.tree(),
    queryFn: async () => {
      const qs = includeInactive ? "?include_inactive=true" : "";
      const { data } = await apiClient.get<ApiResponse<SecurityTaxonomyTreeNode[]>>(
        `${BASE}/tree${qs}`,
      );
      return data.data;
    },
  });
}

export function useTaxonomyDetail(id: string | null | undefined) {
  return useQuery<SecurityTaxonomy>({
    queryKey: keys.detail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<SecurityTaxonomy>>(`${BASE}/${id}`);
      return data.data;
    },
  });
}

export function useTaxonomyAuditLog(
  id: string | null | undefined,
  changeType?: TaxonomyChangeType,
  limit = 50,
) {
  return useQuery<TaxonomyAuditLogEntry[]>({
    queryKey: keys.audit(id ?? "", changeType),
    enabled: Boolean(id),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (changeType) params.set("change_type", changeType);
      params.set("limit", String(limit));
      const { data } = await apiClient.get<ApiResponse<TaxonomyAuditLogEntry[]>>(
        `${BASE}/${id}/audit-log?${params.toString()}`,
      );
      return data.data;
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useCreateTaxonomy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateTaxonomyPayload) => {
      const { data } = await apiClient.post<ApiResponse<SecurityTaxonomy>>(BASE, payload);
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useUpdateTaxonomy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: UpdateTaxonomyPayload }) => {
      const { data } = await apiClient.patch<ApiResponse<SecurityTaxonomy>>(
        `${BASE}/${id}`,
        payload,
      );
      return data.data;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.detail(vars.id) });
      qc.invalidateQueries({ queryKey: keys.lists() });
      qc.invalidateQueries({ queryKey: keys.tree() });
      qc.invalidateQueries({ queryKey: keys.audit(vars.id) });
    },
  });
}

export function useSoftDeleteTaxonomy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
      await apiClient.delete(`${BASE}/${id}`, { data: { reason } });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useForkTaxonomy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, target_tenant_id }: { id: string; target_tenant_id: string }) => {
      const { data } = await apiClient.post<ApiResponse<SecurityTaxonomy>>(
        `${BASE}/${id}/fork`,
        { target_tenant_id },
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.all });
    },
  });
}

export function useRefreshFromGlobal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<ApiResponse<SecurityTaxonomy>>(
        `${BASE}/${id}/refresh-from-global`,
      );
      return data.data;
    },
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: keys.detail(id) });
      qc.invalidateQueries({ queryKey: keys.lists() });
      qc.invalidateQueries({ queryKey: keys.tree() });
      qc.invalidateQueries({ queryKey: keys.audit(id) });
    },
  });
}

export function useAddNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      taxonomy_id, payload,
    }: { taxonomy_id: string; payload: CreateNotificationPayload }) => {
      const { data } = await apiClient.post<ApiResponse<TaxonomyNotification>>(
        `${BASE}/${taxonomy_id}/notifications`,
        payload,
      );
      return data.data;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.detail(vars.taxonomy_id) });
    },
  });
}

export function useRemoveNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      taxonomy_id, notification_id,
    }: { taxonomy_id: string; notification_id: string }) => {
      await apiClient.delete(
        `${BASE}/${taxonomy_id}/notifications/${notification_id}`,
      );
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.detail(vars.taxonomy_id) });
    },
  });
}

export function useAddCatalogMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      taxonomy_id, payload,
    }: { taxonomy_id: string; payload: CreateCatalogMappingPayload }) => {
      const { data } = await apiClient.post<ApiResponse<TaxonomyCatalogMapping>>(
        `${BASE}/${taxonomy_id}/catalog-mappings`,
        payload,
      );
      return data.data;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.detail(vars.taxonomy_id) });
    },
  });
}

export function useSetDefaultCatalogMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      taxonomy_id, mapping_id,
    }: { taxonomy_id: string; mapping_id: string }) => {
      const { data } = await apiClient.patch<ApiResponse<TaxonomyCatalogMapping>>(
        `${BASE}/${taxonomy_id}/catalog-mappings/${mapping_id}/set-default`,
      );
      return data.data;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.detail(vars.taxonomy_id) });
    },
  });
}

export function useRemoveCatalogMapping() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      taxonomy_id, mapping_id,
    }: { taxonomy_id: string; mapping_id: string }) => {
      await apiClient.delete(
        `${BASE}/${taxonomy_id}/catalog-mappings/${mapping_id}`,
      );
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: keys.detail(vars.taxonomy_id) });
    },
  });
}
