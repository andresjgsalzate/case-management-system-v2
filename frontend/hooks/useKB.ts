import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { KBArticle, KBTag, ApiResponse } from "@/lib/types";

const KB_KEY = "kb-articles";

export function useKBArticles(status?: string) {
  return useQuery({
    queryKey: [KB_KEY, status],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBArticle[]>>("/kb/articles", {
        params: status ? { status } : undefined,
      });
      return data.data ?? [];
    },
  });
}

export function useKBArticle(id: string) {
  return useQuery({
    queryKey: [KB_KEY, id],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBArticle>>(`/kb/articles/${id}`);
      return data.data;
    },
    enabled: !!id,
  });
}

export function useKBTags() {
  return useQuery({
    queryKey: ["kb-tags"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBTag[]>>("/kb/tags");
      return data.data ?? [];
    },
    staleTime: 10 * 60_000,
  });
}

export function useCreateKBArticle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      title: string;
      content_json: Record<string, unknown>;
      content_text: string;
      tag_ids?: string[];
    }) => {
      const { data } = await apiClient.post<ApiResponse<KBArticle>>("/kb/articles", payload);
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [KB_KEY] }),
  });
}

export function useTransitionKBArticle(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { to_status: string; comment?: string }) => {
      const { data } = await apiClient.post<ApiResponse<KBArticle>>(
        `/kb/articles/${id}/transitions`,
        payload
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [KB_KEY] }),
  });
}
