import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  ServiceCatalogCategory,
  ServiceCatalogField,
  ServiceCatalogItem,
} from "@/lib/types";

const CATEGORIES_KEY = "service-catalog-categories";
const ITEMS_KEY = "service-catalog-items";
const FIELDS_KEY = "service-catalog-fields";

// ── Categories ────────────────────────────────────────────────────────────────

export function useServiceCategories() {
  return useQuery({
    queryKey: [CATEGORIES_KEY],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ServiceCatalogCategory[]>>(
        "/service-catalog/categories",
      );
      return data.data ?? [];
    },
  });
}

export function useCreateServiceCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dto: {
      name: string;
      slug: string;
      description?: string;
      icon?: string;
      color?: string;
      sort_order?: number;
    }) => {
      const { data } = await apiClient.post<ApiResponse<ServiceCatalogCategory>>(
        "/service-catalog/categories",
        dto,
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [CATEGORIES_KEY] }),
  });
}

export function useUpdateServiceCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      dto,
    }: {
      id: string;
      dto: Partial<{
        name: string;
        description: string;
        icon: string;
        color: string;
        is_active: boolean;
        sort_order: number;
      }>;
    }) => {
      const { data } = await apiClient.patch<ApiResponse<ServiceCatalogCategory>>(
        `/service-catalog/categories/${id}`,
        dto,
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [CATEGORIES_KEY] }),
  });
}

export function useDeleteServiceCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/service-catalog/categories/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [CATEGORIES_KEY] }),
  });
}

// ── Items ─────────────────────────────────────────────────────────────────────

export function useServiceItems(categoryId?: string | null) {
  return useQuery({
    queryKey: [ITEMS_KEY, categoryId ?? null],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ServiceCatalogItem[]>>(
        "/service-catalog/items",
        { params: categoryId ? { category_id: categoryId } : undefined },
      );
      return data.data ?? [];
    },
  });
}

export function useServiceItem(id?: string) {
  return useQuery({
    queryKey: [ITEMS_KEY, id],
    enabled: !!id,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ServiceCatalogItem>>(
        `/service-catalog/items/${id}`,
      );
      return data.data;
    },
  });
}

export function useCreateServiceItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dto: {
      category_id: string;
      name: string;
      slug: string;
      description?: string;
      default_priority_id?: string | null;
      default_team_id?: string | null;
      default_level?: number;
      sla_policy_id?: string | null;
      sort_order?: number;
    }) => {
      const { data } = await apiClient.post<ApiResponse<ServiceCatalogItem>>(
        "/service-catalog/items",
        dto,
      );
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [ITEMS_KEY] });
      qc.invalidateQueries({ queryKey: [CATEGORIES_KEY] });
    },
  });
}

export function useUpdateServiceItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      dto,
    }: {
      id: string;
      dto: Partial<{
        category_id: string;
        name: string;
        description: string;
        default_priority_id: string | null;
        default_team_id: string | null;
        default_level: number;
        sla_policy_id: string | null;
        is_active: boolean;
        sort_order: number;
      }>;
    }) => {
      const { data } = await apiClient.patch<ApiResponse<ServiceCatalogItem>>(
        `/service-catalog/items/${id}`,
        dto,
      );
      return data.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: [ITEMS_KEY] });
      qc.invalidateQueries({ queryKey: [ITEMS_KEY, vars.id] });
      qc.invalidateQueries({ queryKey: [CATEGORIES_KEY] });
    },
  });
}

export function useDeleteServiceItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/service-catalog/items/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [ITEMS_KEY] });
      qc.invalidateQueries({ queryKey: [CATEGORIES_KEY] });
    },
  });
}

// ── Fields ────────────────────────────────────────────────────────────────────

export function useItemFields(itemId?: string) {
  return useQuery({
    queryKey: [FIELDS_KEY, itemId],
    enabled: !!itemId,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<ServiceCatalogField[]>>(
        `/service-catalog/items/${itemId}/fields`,
      );
      return data.data ?? [];
    },
  });
}

export function useCreateField() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dto: {
      item_id: string;
      field_key: string;
      label: string;
      field_type: string;
      is_required?: boolean;
      placeholder?: string;
      help_text?: string;
      options?: { value: string; label: string }[];
      validation?: Record<string, unknown>;
      sort_order?: number;
    }) => {
      const { data } = await apiClient.post<ApiResponse<ServiceCatalogField>>(
        "/service-catalog/fields",
        dto,
      );
      return data.data;
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: [FIELDS_KEY, vars.item_id] });
      qc.invalidateQueries({ queryKey: [ITEMS_KEY] });
    },
  });
}

export function useUpdateField() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      dto,
    }: {
      id: string;
      dto: Partial<{
        label: string;
        field_type: string;
        is_required: boolean;
        placeholder: string;
        help_text: string;
        options: { value: string; label: string }[];
        validation: Record<string, unknown>;
        sort_order: number;
      }>;
    }) => {
      const { data } = await apiClient.patch<ApiResponse<ServiceCatalogField>>(
        `/service-catalog/fields/${id}`,
        dto,
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [FIELDS_KEY] }),
  });
}

export function useDeleteField() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/service-catalog/fields/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [FIELDS_KEY] });
      qc.invalidateQueries({ queryKey: [ITEMS_KEY] });
    },
  });
}

export function useReorderFields() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      itemId,
      orderedIds,
    }: {
      itemId: string;
      orderedIds: string[];
    }) => {
      const { data } = await apiClient.post<ApiResponse<ServiceCatalogField[]>>(
        `/service-catalog/items/${itemId}/fields/reorder`,
        { ordered_ids: orderedIds },
      );
      return data.data ?? [];
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: [FIELDS_KEY, vars.itemId] }),
  });
}
