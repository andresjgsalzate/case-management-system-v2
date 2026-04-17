import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import type { Case, ApiResponse } from "@/lib/types";

export interface CaseNote {
  id: string;
  user_id: string;
  sender_name: string;
  content: string;
  created_at: string;
}

const CASES_KEY = "cases";
const ARCHIVED_KEY = "cases-archived";

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

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users");
      return (data.data ?? []) as { id: string; full_name: string; email: string }[];
    },
    staleTime: 5 * 60_000,
  });
}

export interface TeamMember {
  user_id: string;
  full_name: string | null;
  email: string | null;
  team_role: string;
}

export interface Team {
  id: string;
  name: string;
  description: string | null;
  members: TeamMember[];
}

export function useTeams() {
  return useQuery<Team[]>({
    queryKey: ["teams"],
    queryFn: async () => {
      const { data } = await apiClient.get("/teams");
      return (data.data ?? []) as Team[];
    },
    staleTime: 2 * 60_000,
  });
}

export function useTransitionCase(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { target_status_id: string; solution_description?: string }) => {
      const { data } = await apiClient.post(`/cases/${caseId}/transition`, payload);
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [CASES_KEY, caseId] });
      qc.invalidateQueries({ queryKey: [CASES_KEY] });
    },
  });
}

export function useAssignCase(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { assigned_to: string | null; team_id?: string | null }) => {
      const { data } = await apiClient.post(`/cases/${caseId}/assign`, payload);
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [CASES_KEY, caseId] });
      qc.invalidateQueries({ queryKey: [CASES_KEY] });
    },
  });
}

export function useArchiveCase(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await apiClient.post(`/cases/${caseId}/archive`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [CASES_KEY] });
      qc.invalidateQueries({ queryKey: [ARCHIVED_KEY] });
    },
  });
}

export function useArchivedCases(params?: { search?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: [ARCHIVED_KEY, params],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: Case[]; total: number; page: number; page_size: number }>(
        "/cases/archived",
        { params }
      );
      return data;
    },
    staleTime: 30_000,
  });
}

export function useRestoreCase(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await apiClient.post(`/cases/${caseId}/restore`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [ARCHIVED_KEY] });
      qc.invalidateQueries({ queryKey: [CASES_KEY] });
    },
  });
}

// ── Notes ──────────────────────────────────────────────────────────────────

export function useCaseNotes(caseId: string) {
  return useQuery({
    queryKey: ["notes", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/cases/${caseId}/notes`);
      return (data.data ?? []) as CaseNote[];
    },
    enabled: !!caseId,
  });
}

export function useCreateNote(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (content: string) => {
      const { data } = await apiClient.post(`/cases/${caseId}/notes`, { content });
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes", caseId] }),
  });
}

export function useUpdateNote(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ noteId, content }: { noteId: string; content: string }) => {
      const { data } = await apiClient.patch(`/cases/${caseId}/notes/${noteId}`, { content });
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes", caseId] }),
  });
}

export function useDeleteNote(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (noteId: string) => {
      await apiClient.delete(`/cases/${caseId}/notes/${noteId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes", caseId] }),
  });
}

// ── Time Entries ────────────────────────────────────────────────────────────

export interface TimeEntry {
  id: string;
  entry_type: "auto" | "manual";
  minutes: number;
  description: string | null;
  created_at: string;
}

export interface ActiveTimer {
  id: string;
  case_id: string;
  started_at: string;
}

export function useActiveTimer() {
  return useQuery({
    queryKey: ["active-timer"],
    queryFn: async () => {
      const { data } = await apiClient.get("/time-entries/timer/active");
      return (data.data ?? null) as ActiveTimer | null;
    },
    refetchInterval: 5000,
  });
}

export function useTimeEntries(caseId: string) {
  return useQuery({
    queryKey: ["time-entries", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/cases/${caseId}/time-entries`);
      return data.data as { entries: TimeEntry[]; total_minutes: number };
    },
    enabled: !!caseId,
  });
}

export function useStartTimer(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post(`/cases/${caseId}/time-entries/timer/start`);
      return data.data as ActiveTimer;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["active-timer"] });
      qc.invalidateQueries({ queryKey: ["time-entries", caseId] });
    },
  });
}

export function useStopTimer(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (description?: string) => {
      const { data } = await apiClient.post("/time-entries/timer/stop", { description: description ?? null });
      return data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["active-timer"] });
      qc.invalidateQueries({ queryKey: ["time-entries", caseId] });
    },
  });
}

export function useManualTimeEntry(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { minutes: number; description?: string }) => {
      const { data } = await apiClient.post(`/cases/${caseId}/time-entries/manual`, payload);
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["time-entries", caseId] }),
  });
}

export function useDeleteTimeEntry(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (entryId: string) => {
      await apiClient.delete(`/time-entries/${entryId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["time-entries", caseId] }),
  });
}

// ── Classification ──────────────────────────────────────────────────────────

export interface ClassificationCriterion {
  id: string;
  order: number;
  name: string;
  score1_description: string;
  score2_description: string;
  score3_description: string;
  is_active: boolean;
}

export interface ClassificationThresholds {
  low_max: number;
  medium_max: number;
}

export interface CaseClassification {
  id: string;
  case_id: string;
  scores: Record<string, number>;   // {criterion_id: 1|2|3}
  total_score: number;
  complexity_level: "baja" | "media" | "alta";
  classified_by: string;
  classified_at: string;
  criteria: ClassificationCriterion[];
}

export function useClassificationCriteria() {
  return useQuery({
    queryKey: ["classification-criteria"],
    queryFn: async () => {
      const { data } = await apiClient.get("/classification-criteria");
      return (data.data ?? []) as ClassificationCriterion[];
    },
    staleTime: 2 * 60_000,
  });
}

export function useClassificationThresholds() {
  return useQuery({
    queryKey: ["classification-thresholds"],
    queryFn: async () => {
      const { data } = await apiClient.get("/classification-thresholds");
      return (data.data ?? { low_max: 6, medium_max: 11 }) as ClassificationThresholds;
    },
    staleTime: 5 * 60_000,
  });
}

export function useCreateCriterion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Omit<ClassificationCriterion, "id" | "is_active">) => {
      const { data } = await apiClient.post("/classification-criteria", payload);
      return data.data as ClassificationCriterion;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["classification-criteria"] }),
  });
}

export function useUpdateCriterion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: Partial<ClassificationCriterion> & { id: string }) => {
      const { data } = await apiClient.put(`/classification-criteria/${id}`, payload);
      return data.data as ClassificationCriterion;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["classification-criteria"] }),
  });
}

export function useDeleteCriterion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/classification-criteria/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["classification-criteria"] }),
  });
}

export function useUpdateThresholds() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ClassificationThresholds) => {
      const { data } = await apiClient.put("/classification-thresholds", payload);
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["classification-thresholds"] }),
  });
}

export function useClassification(caseId: string) {
  return useQuery({
    queryKey: ["classification", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/cases/${caseId}/classification`);
      return (data.data ?? null) as CaseClassification | null;
    },
    enabled: !!caseId,
  });
}

export function useSaveClassification(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (scores: Record<string, number>) => {
      const { data } = await apiClient.post(`/cases/${caseId}/classification`, { scores });
      return data.data as { total_score: number; complexity_level: string };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["classification", caseId] }),
  });
}

// ── SLA ───────────────────────────────────────────────────────────────────────

export interface CaseSLARecord {
  id: string;
  case_id: string;
  started_at: string;
  target_at: string;
  is_breached: boolean;
  breached_at: string | null;
  paused_at: string | null;
  status_paused_at: string | null;
}

export interface SLAIntegrationConfig {
  enabled: boolean;
  pause_on_timer: boolean;
  low_max_hours: number | null;
  medium_max_hours: number | null;
  high_max_hours: number | null;
}

export function useCaseSLA(caseId: string) {
  return useQuery<CaseSLARecord | null>({
    queryKey: ["sla-record", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: CaseSLARecord | null }>(`/sla/records/${caseId}`);
      return data.data ?? null;
    },
  });
}

export function useSLAIntegrationConfig() {
  return useQuery<SLAIntegrationConfig>({
    queryKey: ["sla-integration-config"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: SLAIntegrationConfig }>("/sla/integration-config");
      return data.data;
    },
    staleTime: 2 * 60_000,
  });
}

export function useUpdateSLAIntegrationConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SLAIntegrationConfig) => {
      const { data } = await apiClient.put("/sla/integration-config", payload);
      return data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sla-integration-config"] }),
  });
}

// ── Activity ──────────────────────────────────────────────────────────────────

export interface ActivityEntry {
  id: string;
  event_type: string;
  description: string;
  actor_id: string | null;
  actor_name: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export function useCaseActivity(caseId: string) {
  return useQuery<ActivityEntry[]>({
    queryKey: ["activity", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: ActivityEntry[] }>(`/cases/${caseId}/activity`);
      return data.data ?? [];
    },
    enabled: !!caseId,
    refetchInterval: 30_000,
  });
}

// ── Resolution Requests ───────────────────────────────────────────────────────

export interface ResolutionFeedback {
  id: string;
  status: "pending" | "accepted" | "rejected";
  requested_by_name: string;
  requested_at: string;
  responded_by_name: string | null;
  responded_at: string | null;
  rating: number | null;
  observation: string | null;
}

export function useResolutionFeedback(caseId: string) {
  return useQuery<ResolutionFeedback | null>({
    queryKey: ["resolution-feedback", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: ResolutionFeedback | null }>(
        `/cases/${caseId}/resolution-request/result`
      );
      return data.data ?? null;
    },
    enabled: !!caseId,
  });
}

export function useRespondResolutionRequest(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      request_id: string;
      accepted: boolean;
      rating?: number | null;
      observation?: string | null;
    }) => {
      const { data } = await apiClient.post(`/cases/${caseId}/resolution-request/respond`, payload);
      return data.data as { status: string };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resolution-feedback", caseId] });
      qc.invalidateQueries({ queryKey: ["cases", caseId] });
    },
  });
}

// ── Attachments ───────────────────────────────────────────────────────────────

export interface CaseAttachment {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  created_at: string;
}

export function useAttachments(caseId: string) {
  return useQuery<CaseAttachment[]>({
    queryKey: ["attachments", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: CaseAttachment[] }>(
        `/cases/${caseId}/attachments`
      );
      return data.data ?? [];
    },
    enabled: !!caseId,
  });
}

export function useUploadAttachment(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await apiClient.post(
        `/cases/${caseId}/attachments`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data.data as { id: string; original_filename: string };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attachments", caseId] }),
  });
}

export function useDeleteAttachment(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (attachmentId: string) => {
      await apiClient.delete(`/cases/${caseId}/attachments/${attachmentId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attachments", caseId] }),
  });
}

export async function downloadAttachment(caseId: string, attachmentId: string, filename: string) {
  const response = await apiClient.get(
    `/cases/${caseId}/attachments/${attachmentId}/download`,
    { responseType: "blob" }
  );
  const url = URL.createObjectURL(response.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Assignments History ───────────────────────────────────────────────────────

export interface CaseAssignmentEntry {
  id: string;
  assigned_to: string | null;
  assigned_to_name: string | null;
  assigned_by: string | null;
  assigned_by_name: string | null;
  team_id: string | null;
  assigned_at: string;
}

export function useCaseAssignments(caseId: string) {
  return useQuery<CaseAssignmentEntry[]>({
    queryKey: ["assignments", caseId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ data: CaseAssignmentEntry[] }>(
        `/cases/${caseId}/assignments`
      );
      return data.data ?? [];
    },
    enabled: !!caseId,
  });
}
