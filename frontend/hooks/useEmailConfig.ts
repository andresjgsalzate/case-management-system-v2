// frontend/hooks/useEmailConfig.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { ApiResponse } from "@/lib/types";

export interface SmtpConfig {
  id: string;
  host: string;
  port: number;
  username: string | null;
  from_email: string;
  from_name: string;
  use_tls: boolean;
  is_enabled: boolean;
  updated_at: string;
}

export type BlockType =
  | "header" | "hero" | "body" | "text" | "button"
  | "divider" | "footer" | "data_table" | "alert" | "image" | "two_columns";

export interface Block {
  type: BlockType;
  props: Record<string, unknown>;
}

export interface EmailTemplate {
  id: string;
  name: string;
  scope: string;
  blocks: Block[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── SMTP hooks ────────────────────────────────────────────────────────────────

export function useSmtpConfig() {
  return useQuery<SmtpConfig | null>({
    queryKey: ["smtp-config"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<SmtpConfig | null>>("/email-config/smtp");
      return data.data ?? null;
    },
  });
}

export function useSaveSmtpConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<SmtpConfig> & { password?: string }) =>
      apiClient.put("/email-config/smtp", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smtp-config"] }),
  });
}

export function useTestSmtpConfig() {
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ApiResponse<{ success: boolean; message: string }>>(
        "/email-config/smtp/test"
      );
      return data.data!;
    },
  });
}

// ── Email template hooks ──────────────────────────────────────────────────────

export function useEmailTemplates() {
  return useQuery<EmailTemplate[]>({
    queryKey: ["email-templates"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<EmailTemplate[]>>("/email-config/templates");
      return data.data ?? [];
    },
  });
}

export function useCreateEmailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; scope: string; blocks: Block[] }) => {
      const { data } = await apiClient.post<ApiResponse<EmailTemplate>>("/email-config/templates", body);
      return data.data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}

export function useUpdateEmailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string } & Partial<Pick<EmailTemplate, "name" | "scope" | "blocks" | "is_active">>) => {
      const { data } = await apiClient.put<ApiResponse<EmailTemplate>>(`/email-config/templates/${id}`, body);
      return data.data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}

export function useDeleteEmailTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/email-config/templates/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}
