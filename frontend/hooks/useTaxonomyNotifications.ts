// CRUD for the per-taxonomy notification routing rules (which team
// gets pinged on which phase via which channel, with optional
// escalation). Backed by /security-taxonomies/{id}/notifications.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateNotificationPayload,
  TaxonomyNotification,
} from "@/lib/types";

const keys = {
  all: ["taxonomy-notifications"] as const,
  list: (taxonomyId: string) =>
    [...keys.all, "list", taxonomyId] as const,
};

export function useTaxonomyNotifications(taxonomyId: string | null) {
  return useQuery<TaxonomyNotification[]>({
    queryKey: keys.list(taxonomyId ?? ""),
    enabled: !!taxonomyId,
    staleTime: 60 * 1000,
    queryFn: async () => {
      const { data } = await apiClient.get<
        ApiResponse<TaxonomyNotification[]>
      >(`/security-taxonomies/${taxonomyId}/notifications`);
      return data.data;
    },
  });
}

export function useAddTaxonomyNotification(taxonomyId: string) {
  const qc = useQueryClient();
  return useMutation<TaxonomyNotification, Error, CreateNotificationPayload>({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<
        ApiResponse<TaxonomyNotification>
      >(`/security-taxonomies/${taxonomyId}/notifications`, payload);
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.list(taxonomyId) });
    },
  });
}

export function useRemoveTaxonomyNotification(taxonomyId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (notificationId) => {
      await apiClient.delete(
        `/security-taxonomies/${taxonomyId}/notifications/${notificationId}`,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.list(taxonomyId) });
    },
  });
}
