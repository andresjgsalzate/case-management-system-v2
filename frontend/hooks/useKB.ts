import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { KBArticle, KBArticleVersion, KBTag, ApiResponse } from "@/lib/types";

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

export function useUpdateKBArticle(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      title?: string;
      content_json?: Record<string, unknown>;
      content_text?: string;
      tag_ids?: string[];
    }) => {
      const { data } = await apiClient.patch<ApiResponse<KBArticle>>(
        `/kb/articles/${id}`,
        payload
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [KB_KEY] }),
  });
}

export function useSubmitKBFeedback(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { is_helpful: boolean }) => {
      const { data } = await apiClient.post<ApiResponse<{ id: string; is_helpful: boolean }>>(
        `/kb/articles/${id}/feedback`,
        payload
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [KB_KEY, id] }),
  });
}

export function useToggleKBFavorite(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ApiResponse<{ favorited: boolean }>>(
        `/kb/articles/${id}/favorite`
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [KB_KEY, id] }),
  });
}

export function useKBVersions(id: string) {
  return useQuery({
    queryKey: [KB_KEY, id, "versions"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBArticleVersion[]>>(
        `/kb/articles/${id}/versions`
      );
      return data.data ?? [];
    },
    enabled: !!id,
  });
}
