// Frontend hooks for Sub-spec 03 — Prioritization Engine.
// Pattern follows useSecurityTaxonomies.ts: @tanstack/react-query + apiClient.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  ApiResponse,
  CreateFormulaVersionPayload,
  PrioritizationCriterion,
  PrioritizationFormula,
  PrioritizationScale,
  PriorityCalculation,
} from "@/lib/types";

const BASE = "/prioritization";

// ── Query keys ───────────────────────────────────────────────────────────────

const keys = {
  all: ["prioritization"] as const,
  criteria: () => [...keys.all, "criteria"] as const,
  scales: (criterionId: string) => [...keys.all, "scales", criterionId] as const,
  formulas: () => [...keys.all, "formulas"] as const,
  formulaList: (filters: FormulaListFilters) =>
    [...keys.formulas(), filters] as const,
  formulaDetail: (id: string) => [...keys.formulas(), "detail", id] as const,
  formulaActiveByKey: (logicalKey: string) =>
    [...keys.formulas(), "by-key", logicalKey, "active"] as const,
  caseCalculations: (caseId: string) =>
    ["cases", caseId, "priority-calculations"] as const,
};

export interface FormulaListFilters {
  logical_key?: string;
  active_only?: boolean;
}

// ── Reads ────────────────────────────────────────────────────────────────────

export function usePrioritizationCriteria() {
  return useQuery<PrioritizationCriterion[]>({
    queryKey: keys.criteria(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PrioritizationCriterion[]>>(
        `${BASE}/criteria`,
      );
      return data.data;
    },
  });
}

export function useCriterionScales(criterionId: string | null | undefined) {
  return useQuery<PrioritizationScale[]>({
    queryKey: keys.scales(criterionId ?? ""),
    enabled: Boolean(criterionId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PrioritizationScale[]>>(
        `${BASE}/criteria/${criterionId}/scales`,
      );
      return data.data;
    },
  });
}

export function usePrioritizationFormulas(filters: FormulaListFilters = {}) {
  return useQuery<PrioritizationFormula[]>({
    queryKey: keys.formulaList(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.logical_key) params.set("logical_key", filters.logical_key);
      if (filters.active_only) params.set("active_only", "true");
      const qs = params.toString();
      const { data } = await apiClient.get<ApiResponse<PrioritizationFormula[]>>(
        `${BASE}/formulas${qs ? `?${qs}` : ""}`,
      );
      return data.data;
    },
  });
}

export function useFormulaDetail(id: string | null | undefined) {
  return useQuery<PrioritizationFormula>({
    queryKey: keys.formulaDetail(id ?? ""),
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PrioritizationFormula>>(
        `${BASE}/formulas/${id}`,
      );
      return data.data;
    },
  });
}

export function useActiveFormulaByKey(logicalKey: string | null | undefined) {
  return useQuery<PrioritizationFormula>({
    queryKey: keys.formulaActiveByKey(logicalKey ?? ""),
    enabled: Boolean(logicalKey),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PrioritizationFormula>>(
        `${BASE}/formulas/by-key/${logicalKey}/active`,
      );
      return data.data;
    },
  });
}

export function useCasePriorityCalculations(
  caseId: string | null | undefined,
  limit = 50,
) {
  return useQuery<PriorityCalculation[]>({
    queryKey: keys.caseCalculations(caseId ?? ""),
    enabled: Boolean(caseId),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PriorityCalculation[]>>(
        `/cases/${caseId}/priority-calculations?limit=${limit}`,
      );
      return data.data;
    },
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

export function useCreateFormulaVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateFormulaVersionPayload) => {
      const { data } = await apiClient.post<ApiResponse<PrioritizationFormula>>(
        `${BASE}/formulas`,
        payload,
      );
      return data.data;
    },
    onSuccess: (formula) => {
      qc.invalidateQueries({ queryKey: keys.formulas() });
      qc.invalidateQueries({
        queryKey: keys.formulaActiveByKey(formula.logical_key),
      });
    },
  });
}

export function useRecalculatePriority() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (caseId: string) => {
      const { data } = await apiClient.post<ApiResponse<PriorityCalculation>>(
        `/cases/${caseId}/recalculate-priority`,
      );
      return data.data;
    },
    onSuccess: (_data, caseId) => {
      qc.invalidateQueries({ queryKey: keys.caseCalculations(caseId) });
      qc.invalidateQueries({ queryKey: ["cases", caseId] });
    },
  });
}

export function usePromoteCaseToNewFormulaVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (caseId: string) => {
      const { data } = await apiClient.post<ApiResponse<PriorityCalculation>>(
        `/cases/${caseId}/promote-to-formula-version`,
      );
      return data.data;
    },
    onSuccess: (_data, caseId) => {
      qc.invalidateQueries({ queryKey: keys.caseCalculations(caseId) });
      qc.invalidateQueries({ queryKey: ["cases", caseId] });
    },
  });
}
