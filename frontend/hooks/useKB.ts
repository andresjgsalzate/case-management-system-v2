import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type {
  KBArticle,
  KBArticleVersion,
  KBTag,
  KBDocumentType,
  KBReviewHistoryResponse,
  KBFeedbackCheck,
  KBFeedbackStats,
  ApiResponse,
} from "@/lib/types";

const KB_KEY = "kb-articles";
const DOC_TYPES_KEY = "kb-document-types";

export function useKBArticles(status?: string, tagSlug?: string) {
  return useQuery({
    queryKey: [KB_KEY, status, tagSlug],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (status) params.status = status;
      if (tagSlug) params.tag_slug = tagSlug;
      const { data } = await apiClient.get<ApiResponse<KBArticle[]>>("/kb/articles", {
        params: Object.keys(params).length ? params : undefined,
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

export function useCreateKBTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string; slug: string }) => {
      const { data } = await apiClient.post<ApiResponse<KBTag>>("/kb/tags", payload);
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["kb-tags"] }),
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
      document_type_id?: string | null;
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
      document_type_id?: string | null;
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

// ─── Document Types ──────────────────────────────────────────────────────────

export function useDocumentTypes(includeInactive = false) {
  return useQuery({
    queryKey: [DOC_TYPES_KEY, includeInactive],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBDocumentType[]>>(
        "/kb/document-types",
        { params: includeInactive ? { include_inactive: true } : undefined }
      );
      return data.data ?? [];
    },
    staleTime: 10 * 60_000,
  });
}

export function useCreateDocumentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      code: string;
      name: string;
      icon: string;
      color: string;
      sort_order?: number;
    }) => {
      const { data } = await apiClient.post<ApiResponse<KBDocumentType>>(
        "/kb/document-types",
        payload
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [DOC_TYPES_KEY] }),
  });
}

export function useUpdateDocumentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...payload
    }: {
      id: string;
      name?: string;
      icon?: string;
      color?: string;
      sort_order?: number;
      is_active?: boolean;
    }) => {
      const { data } = await apiClient.patch<ApiResponse<KBDocumentType>>(
        `/kb/document-types/${id}`,
        payload
      );
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [DOC_TYPES_KEY] }),
  });
}

export function useDeleteDocumentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/kb/document-types/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: [DOC_TYPES_KEY] }),
  });
}

// ─── Review workflow + feedback queries ──────────────────────────────────────

export function usePendingReview() {
  return useQuery({
    queryKey: [KB_KEY, "pending-review"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBArticle[]>>(
        "/kb/articles/pending-review"
      );
      return data.data ?? [];
    },
  });
}

export function useReviewHistory(id: string) {
  return useQuery({
    queryKey: [KB_KEY, id, "review-history"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBReviewHistoryResponse>>(
        `/kb/articles/${id}/review-history`
      );
      return data.data;
    },
    enabled: !!id,
  });
}

export function useFeedbackCheck(id: string) {
  return useQuery({
    queryKey: [KB_KEY, id, "feedback-check"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBFeedbackCheck>>(
        `/kb/articles/${id}/feedback/check`
      );
      return data.data;
    },
    enabled: !!id,
  });
}

export function useFeedbackStats(id: string) {
  return useQuery({
    queryKey: [KB_KEY, id, "feedback-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<KBFeedbackStats>>(
        `/kb/articles/${id}/feedback/stats`
      );
      return data.data;
    },
    enabled: !!id,
  });
}
