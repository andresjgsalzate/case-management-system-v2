// ─── Core entities ────────────────────────────────────────────────────────────

export interface UserPermission {
  module: string;
  action: string;
  scope: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role_id?: string;
  role_name?: string;
  role_level?: number;
  team_id?: string;
  is_active: boolean;
  avatar_url?: string;
  email_notifications: boolean;
  permissions?: UserPermission[];
  created_at: string;
  updated_at: string;
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  level?: number;
}

export interface Team {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  member_count?: number;
}

// ─── Cases ────────────────────────────────────────────────────────────────────

export type CaseType = 'request' | 'incident' | 'event';

export interface CaseStatus {
  id: string;
  name: string;
  slug: string;
  color?: string;
  is_initial?: boolean;
  is_final?: boolean;
  sort_order?: number;
  allowed_transitions: string[];
}

export interface CasePriority {
  id: string;
  name: string;
  level: number;
  color?: string;
}

export interface Application {
  id: string;
  name: string;
  description?: string;
}

export interface Case {
  id: string;
  case_number: string;
  title: string;
  description?: string;
  complexity: string;
  current_level: number;
  // Status (flat fields from backend DTO)
  status_id: string;
  status_name: string;
  status_slug: string;
  status_color: string;
  // Priority (flat fields from backend DTO)
  priority_id: string;
  priority_name: string;
  priority_color: string;
  // Optional FK fields
  application_id?: string;
  application_name?: string;
  origin_id?: string;
  origin_name?: string;
  service_item_id?: string | null;
  service_item_name?: string | null;
  service_category_id?: string | null;
  service_category_name?: string | null;
  assigned_to?: string;
  assigned_user_name?: string | null;
  team_id?: string;
  created_by: string;
  solution_description?: string | null;
  is_archived: boolean;
  archived_at?: string | null;
  archived_by?: string | null;
  closed_at?: string | null;
  created_at: string;
  updated_at: string;
  // Enriched optional fields (populated by some endpoints)
  assigned_user?: User;
  // Case type and promotion fields
  case_type?: CaseType;
  taxonomy_id?: string | null;
  original_case_number?: string | null;
  original_case_type?: CaseType | null;
  promoted_at?: string | null;
  promoted_by?: string | null;
  pending_triage_until?: string | null;
}

export interface CaseNote {
  id: string;
  case_id: string;
  content: string;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  case_id: string;
  content: string;
  sender_id: string;
  created_at: string;
  edited_at?: string;
}

// ─── Knowledge Base ───────────────────────────────────────────────────────────

export type KBStatus = 'draft' | 'in_review' | 'approved' | 'published' | 'rejected';

export interface KBTag {
  id: string;
  name: string;
  slug: string;
}

export type KBVisibility = "private" | "team" | "public";

export interface KBArticleCaseRef {
  case_number: string;
  case_title: string;
}

export interface KBArticle {
  id: string;
  title: string;
  content_json: Record<string, unknown>;
  content_text: string;
  status: KBStatus;
  version: number;
  created_by_id: string;
  created_by_name?: string | null;
  approved_by_id?: string;
  published_at?: string;
  view_count: number;
  helpful_count: number;
  not_helpful_count: number;
  created_at: string;
  updated_at: string;
  tags?: KBTag[];
  case_refs?: KBArticleCaseRef[];
  document_type_id?: string | null;
  document_type?: KBDocumentTypeRef | null;
  visibility: KBVisibility;
  pending_visibility?: KBVisibility | null;
}

export interface KBArticleVersion {
  id: string;
  version_number: number;
  title: string;
  content_text: string;
  saved_by_id: string;
  created_at: string;
}

export interface KBDocumentType {
  id: string;
  code: string;
  name: string;
  icon: string;
  color: string;
  is_active: boolean;
  sort_order: number;
}

export interface KBDocumentTypeRef {
  id: string;
  code: string;
  name: string;
  icon: string;
  color: string;
}

export interface KBReviewEvent {
  id: string;
  article_id: string;
  actor_id: string;
  from_status: string;
  to_status: string;
  comment: string | null;
  created_at: string;
}

export interface KBReviewHistorySummary {
  submitted: number;
  approved: number;
  rejected: number;
  published: number;
  returned_to_draft: number;
}

export interface KBReviewHistoryResponse {
  events: KBReviewEvent[];
  summary: KBReviewHistorySummary;
}

export interface KBFeedbackCheck {
  has_feedback: boolean;
  is_helpful: boolean | null;
}

export interface KBFeedbackStats {
  helpful_count: number;
  not_helpful_count: number;
  total: number;
  helpful_percentage: number;
}

// ─── Notifications ────────────────────────────────────────────────────────────

export type NotificationType =
  | 'case_assigned'
  | 'case_updated'
  | 'sla_breach'
  | 'kb_review_request'
  | 'mention'
  | 'automation'
  | 'info';

export interface Notification {
  id: string;
  title: string;
  body: string;
  notification_type: NotificationType;
  reference_id?: string;
  reference_type?: string;
  is_read: boolean;
  read_at?: string;
  created_at: string;
}

// ─── Audit ────────────────────────────────────────────────────────────────────

export type AuditAction = 'INSERT' | 'UPDATE' | 'DELETE';

export interface AuditLog {
  id: string;
  action: AuditAction;
  entity_type: string;
  entity_id: string;
  entity_label?: string | null;
  changes?: Record<string, { old: unknown; new: unknown } | unknown>;
  before_snapshot?: Record<string, unknown> | null;
  actor_id?: string;
  actor_name?: string | null;
  correlation_id?: string | null;
  user_agent?: string | null;
  request_path?: string | null;
  ip_address?: string;
  created_at: string;
}

// ─── Metrics ──────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  open_cases: number;
  created_today: number;
  resolved_today: number;
  unassigned: number;
  solved_cases: number;
  at_risk_sla: number;
  stale_backlog: number;
  reopened_cases: number;
  total_closed_ever: number;
  reopen_rate_pct: number;
}

export interface LevelCount {
  level: number;
  count: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface TrendPoint {
  date: string;
  count: number;
}

// ─── Dispositions ─────────────────────────────────────────────────────────────

export interface DispositionCategory {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
}

export interface Disposition {
  id: string;
  category_id: string;
  // Legacy fields
  title?: string | null;
  content?: string | null;
  // Technical fields
  date?: string | null;
  case_number?: string | null;
  item_name?: string | null;
  storage_path?: string | null;
  revision_number?: string | null;
  observations?: string | null;
  is_active: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

// ─── API wrapper ──────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total?: number;
  page?: number;
  page_size?: number;
}

// ─── Case transfers ───────────────────────────────────────────────────────────

export type CaseTransferType = 'escalate' | 'reassign' | 'de-escalate';

export interface CaseTransfer {
  id: string;
  case_id: string;
  from_user_id: string | null;
  from_level: number;
  to_user_id: string;
  to_team_id: string;
  to_level: number;
  transfer_type: CaseTransferType;
  reason: string;
  created_at: string;
}

export interface CasePermissions {
  canRead: boolean;
  canUpdate: boolean;
  canTransition: boolean;
  canTransfer: boolean;
  canComment: boolean;
  canAttach: boolean;
}

// ─── KB ↔ Cases associations ──────────────────────────────────────────────────

export interface ArticleCaseRef {
  case_id: string;
  case_number: string;
  case_title: string;
  linked_at: string;
  can_access: boolean;
}

export interface CaseKBArticleRef {
  id: string;
  title: string;
  status: KBStatus;
  document_type: KBDocumentTypeRef | null;
  linked_at: string;
}

// ─── Service Catalog ──────────────────────────────────────────────────────────

export type ServiceFieldType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "datetime"
  | "select"
  | "radio"
  | "checkbox"
  | "multiselect"
  | "email"
  | "phone";

export interface ServiceFieldOption {
  value: string;
  label: string;
}

export interface ServiceCatalogCategory {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  icon?: string | null;
  color?: string | null;
  is_active: boolean;
  sort_order: number;
  item_count: number;
}

export interface ServiceCatalogItem {
  id: string;
  category_id: string;
  category_name?: string | null;
  name: string;
  slug: string;
  description?: string | null;
  default_priority_id?: string | null;
  default_team_id?: string | null;
  default_level: number;
  sla_policy_id?: string | null;
  is_active: boolean;
  sort_order: number;
  field_count: number;
}

export interface ServiceCatalogField {
  id: string;
  item_id: string;
  field_key: string;
  label: string;
  field_type: ServiceFieldType;
  is_required: boolean;
  placeholder?: string | null;
  help_text?: string | null;
  options?: ServiceFieldOption[] | null;
  validation?: Record<string, unknown> | null;
  sort_order: number;
}

export interface CaseCustomValue {
  field_id: string;
  field_key: string;
  label: string;
  field_type: ServiceFieldType;
  value: string | null;
  options?: ServiceFieldOption[] | null;
}

// ─── Sub-spec 02 — Security Taxonomies ────────────────────────────────────────

export type TLP = "white" | "green" | "amber" | "red";
export type TriageMode = "auto" | "delegate_to_n8n";
export type TaxonomyDefaultCaseType = "event" | "incident";
export type NotifyPhase =
  | "triage" | "created" | "critical_priority"
  | "sla_breach" | "resolved" | "promoted";
export type NotifyChannel = "email" | "chat" | "sms" | "all";
export type TaxonomyChangeType =
  | "created" | "updated" | "soft_deleted"
  | "activated" | "forked" | "refreshed_from_global";

export interface SecurityTaxonomy {
  id: string;
  tenant_id: string | null;
  tuic_code: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  attack_type: string | null;
  attack_subtype: string | null;
  internal_impact_context: string | null;
  external_impact_context: string | null;
  managed_by_team_id: string | null;
  default_case_type: TaxonomyDefaultCaseType;
  requires_ticket: boolean;
  triage_mode: TriageMode;
  delegated_workflow_id: string | null;
  triage_timeout_seconds: number;
  tlp_default: TLP;
  prioritization_formula_id: string | null;
  mitre_techniques: string[];
  is_active: boolean;
  forked_from_global_id: string | null;
  forked_from_global_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string | null;
}

// /tree response: same as SecurityTaxonomy + children
export interface SecurityTaxonomyTreeNode extends SecurityTaxonomy {
  children: SecurityTaxonomyTreeNode[];
}

export interface TaxonomyNotification {
  id: string;
  taxonomy_id: string;
  team_id: string;
  notify_phase: NotifyPhase;
  notify_channel: NotifyChannel;
  escalation_minutes: number | null;
}

export interface TaxonomyCatalogMapping {
  id: string;
  taxonomy_id: string;
  service_catalog_item_id: string;
  is_default: boolean;
  priority_order: number;
}

export interface TaxonomyAuditLogEntry {
  id: string;
  taxonomy_id: string;
  changed_by: string;
  changed_at: string;
  change_type: TaxonomyChangeType;
  field_changes: Record<string, { from: unknown; to: unknown } | unknown>;
  reason: string | null;
}

// ── Create / update payloads (router accepts these directly) ──────────────────

export interface CreateTaxonomyPayload {
  tenant_id?: string | null;
  tuic_code: string;
  name: string;
  description?: string | null;
  parent_id?: string | null;
  attack_type?: string | null;
  attack_subtype?: string | null;
  internal_impact_context?: string | null;
  external_impact_context?: string | null;
  managed_by_team_id?: string | null;
  default_case_type?: TaxonomyDefaultCaseType;
  requires_ticket?: boolean;
  triage_mode?: TriageMode;
  delegated_workflow_id?: string | null;
  triage_timeout_seconds?: number;
  tlp_default?: TLP;
  prioritization_formula_id?: string | null;
  mitre_techniques?: string[];
}

export interface UpdateTaxonomyPayload {
  name?: string;
  description?: string | null;
  parent_id?: string | null;
  attack_type?: string | null;
  attack_subtype?: string | null;
  internal_impact_context?: string | null;
  external_impact_context?: string | null;
  managed_by_team_id?: string | null;
  default_case_type?: TaxonomyDefaultCaseType;
  requires_ticket?: boolean;
  triage_mode?: TriageMode;
  delegated_workflow_id?: string | null;
  triage_timeout_seconds?: number;
  tlp_default?: TLP;
  prioritization_formula_id?: string | null;
  mitre_techniques?: string[];
  is_active?: boolean;
}

export interface CreateNotificationPayload {
  team_id: string;
  notify_phase: NotifyPhase;
  notify_channel?: NotifyChannel;
  escalation_minutes?: number | null;
}

export interface CreateCatalogMappingPayload {
  service_catalog_item_id: string;
  is_default?: boolean;
  priority_order?: number;
}

// ── Sub-spec 03 — Prioritization Engine ──────────────────────────────────────

export type PrioritizationDataSource =
  | "taxonomy_field"
  | "case_custom_value"
  | "asset_field"
  | "derived";

export type MissingDataStrategy = "use_default" | "skip";

export interface PrioritizationCriterion {
  id: string;
  tenant_id: string | null;
  code: string;
  name: string;
  description: string | null;
  data_source: PrioritizationDataSource;
  source_field_key: string | null;
  missing_data_strategy: MissingDataStrategy;
  default_value: number | null;
  is_active: boolean;
  sort_order: number;
}

export interface PrioritizationScale {
  id: string;
  criterion_id: string;
  label: string;
  numeric_value: number;
  color: string | null;
  sort_order: number;
}

export interface PrioritizationFormula {
  id: string;
  tenant_id: string | null;
  logical_key: string;
  version: number;
  name: string;
  description: string | null;
  is_active: boolean;
  effective_from: string;
  effective_to: string | null;
  superseded_by_id: string | null;
  created_at: string;
  created_by: string;
}

export interface FormulaCriterionWeight {
  code: string;
  weight: string; // Decimal serialized as string for precision
}

export interface FormulaThresholdEntry {
  min_value: string;
  max_value: string;
  priority_name: string; // Baja | Media | Alta | Critica
}

// Read-side detail rows (returned by GET /formulas/{id})
export interface FormulaWeightDetail {
  criterion_id: string;
  criterion_code: string;
  criterion_name: string;
  weight: string;
}

export interface FormulaThresholdDetail {
  id: string;
  min_value: string;
  max_value: string;
  priority_id: string;
  priority_name: string;
}

export interface PrioritizationFormulaDetail extends PrioritizationFormula {
  criteria_weights: FormulaWeightDetail[];
  thresholds: FormulaThresholdDetail[];
}

export interface CreateFormulaVersionPayload {
  tenant_id?: string | null;
  logical_key: string;
  base_version_id?: string | null;
  name: string;
  description?: string | null;
  criteria_weights: FormulaCriterionWeight[];
  thresholds: FormulaThresholdEntry[];
}

export type CalculationTriggeredBy =
  | "case_created"
  | "case_updated"
  | "manual"
  | "formula_promoted"
  | "scheduled";

export interface PriorityCalculation {
  id: string;
  case_id: string;
  formula_id: string;
  formula_version: number;
  inputs: Record<string, unknown>;
  weighted_sum: string; // Decimal as string
  resulting_priority_id: string;
  calculated_at: string;
  triggered_by: CalculationTriggeredBy;
  triggered_by_user: string | null;
}

// ── Sub-spec 04 — Inbound Integrations & Wazuh Adapter ───────────────────────

export type SourceType =
  | "wazuh"
  | "splunk"
  | "sentinel"
  | "crowdstrike"
  | "qradar"
  | "wazuh_velociraptor"
  | "custom";

export type AuthMethod = "hmac" | "api_key" | "bearer" | "none";

export type InboundEventStatus =
  | "pending"
  | "processing"
  | "processed"
  | "failed"
  | "duplicate";

export interface IntegrationSource {
  id: string;
  tenant_id: string | null;
  name: string;
  source_type: SourceType;
  auth_method: AuthMethod;
  auth_header_name: string | null;
  default_service_item_id: string | null;
  default_priority_id: string | null;
  is_active: boolean;
  rate_limit_per_minute: number | null;
  last_event_received_at: string | null;
  last_event_processed_at: string | null;
  total_events_received: number;
  total_events_failed: number;
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface CreateIntegrationSourcePayload {
  tenant_id?: string | null;
  name: string;
  source_type: SourceType;
  auth_method: AuthMethod;
  auth_header_name?: string | null;
  default_service_item_id?: string | null;
  default_priority_id?: string | null;
  rate_limit_per_minute?: number | null;
}

export interface UpdateIntegrationSourcePayload {
  name?: string;
  auth_header_name?: string | null;
  default_service_item_id?: string | null;
  default_priority_id?: string | null;
  rate_limit_per_minute?: number | null;
  is_active?: boolean;
}

export interface CreateSourceResponse {
  source: IntegrationSource;
  plaintext_secret: string;
  webhook_url: string | null;
}

export interface RotateSecretResponse {
  source_id: string;
  plaintext_secret: string;
}

export type WazuhMatchStrategy =
  | "rule_id"
  | "rule_groups_any"
  | "rule_groups_all"
  | "level_min"
  | "level_range";

export interface WazuhRuleMapping {
  id: string;
  tenant_id: string | null;
  source_id: string | null;
  match_strategy: WazuhMatchStrategy;
  match_value: Record<string, unknown>;
  taxonomy_id: string;
  priority_order: number;
  is_active: boolean;
  description: string | null;
}

// ── Sub-spec 05 — n8n Bridge ─────────────────────────────────────────────────

export type PlaybookRunStatus =
  | "triggered"
  | "running"
  | "completed"
  | "failed"
  | "timeout"
  | "cancelled";

export type PlaybookRunTriggeredBy =
  | "auto_triage"
  | "automation_rule"
  | "manual"
  | "approval_resume";

export interface PlaybookRun {
  id: string;
  tenant_id: string;
  case_id: string;
  workflow_url: string;
  workflow_id: string | null;
  triggered_at: string;
  completed_at: string | null;
  triggered_by: PlaybookRunTriggeredBy;
  triggered_by_user: string | null;
  status: PlaybookRunStatus;
  last_callback_at: string | null;
  callback_count: number;
  n8n_execution_id: string | null;
  error: string | null;
  final_decision: string | null;
  final_decision_data: Record<string, unknown> | null;
}

export interface PlaybookRunCallback {
  id: string;
  playbook_run_id: string;
  received_at: string;
  action: string;
  payload: Record<string, unknown>;
  success: boolean;
  error: string | null;
  response_payload: Record<string, unknown> | null;
}

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "timeout"
  | "cancelled";

export interface ApprovalRequest {
  id: string;
  tenant_id: string;
  case_id: string;
  playbook_run_id: string | null;
  requested_action: string;
  action_category: string;
  context_payload: Record<string, unknown>;
  requested_by_workflow: string;
  resume_url: string;
  status: ApprovalStatus;
  approver_user_id: string | null;
  decided_at: string | null;
  decided_reason: string | null;
  timeout_at: string;
  resume_attempted_at: string | null;
  resume_succeeded: boolean;
  resume_error: string | null;
  created_at: string;
}

export interface ManualTriggerWorkflowPayload {
  workflow_url: string;
  extra_context?: Record<string, unknown> | null;
}

export interface ApprovalDecidePayload {
  decision: "approved" | "rejected";
  reason?: string | null;
}


// ── Sub-spec 06 — Operational Center UI ─────────────────────────────────────

export type DashboardKPIs = {
  period_hours: number;
  cases_per_hour: number | null;
  mttr_minutes: number | null;
  mttd_minutes: number | null;
  sla_compliance_pct: number | null;
  false_positive_rate_pct: number | null;
};

export type DashboardRecentEvent = {
  id: string;
  source_id: string;
  received_at: string;
  status: string;
  case_id: string | null;
};

export type IntegrationHealthStatus = "healthy" | "degraded" | "down" | "unknown";

export type IntegrationHealthSummary = {
  source_id: string;
  source_name: string | null;
  status: IntegrationHealthStatus;
  recorded_at: string;
  events_received_5min: number;
  events_processed_5min: number;
  events_failed_5min: number;
  avg_latency_ms_5min: number | null;
};

export type IntegrationHealthHistoryPoint = {
  id: string;
  source_id: string;
  source_name: string | null;
  recorded_at: string;
  status: IntegrationHealthStatus;
  events_received_5min: number;
  events_processed_5min: number;
  events_failed_5min: number;
  avg_latency_ms_5min: number | null;
  extra_metrics: Record<string, unknown> | null;
};

export type ApprovalSummary = {
  id: string;
  case_id: string;
  requested_action: string;
  action_category: string;
  requested_by_workflow: string;
  timeout_at: string;
  created_at: string;
};

/** SOC dashboard summary returned by /operational/dashboard/summary.
 * Distinct from the case-management DashboardSummary above; that one is
 * scoped to the existing /metrics page. */
export type SocDashboardSummary = {
  severity_counters: Record<string, number>;
  kpis: DashboardKPIs;
  recent_events: DashboardRecentEvent[];
  integration_health: IntegrationHealthSummary[] | null;
  pending_approvals_count: number | null;
  pending_approvals: ApprovalSummary[] | null;
  generated_at: string;
};

export type AuditSource = "activity" | "audit" | "inbound_event";

export type AuditEvent = {
  source_table: AuditSource | string;
  event_id: string;
  occurred_at: string;
  case_id: string | null;
  actor_id: string | null;
  summary: string;
  extra: Record<string, unknown> | null;
};

export type AuditQueryResultDTO = {
  events: AuditEvent[];
  total: number;
};

export type AuditExplorerFilters = {
  case_id?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  sources?: AuditSource[];
  search?: string | null;
  limit?: number;
  offset?: number;
};

// Approvals inbox row shape (richer than ApprovalSummary — includes
// status/decision fields that the standalone inbox page needs).
export type ApprovalInboxRow = {
  id: string;
  case_id: string;
  playbook_run_id: string | null;
  requested_action: string;
  action_category: string;
  requested_by_workflow: string;
  status: "pending" | "approved" | "rejected" | "timeout" | "cancelled";
  approver_user_id: string | null;
  decided_at: string | null;
  decided_reason: string | null;
  timeout_at: string;
  resume_succeeded: boolean;
  created_at: string;
  context_payload: Record<string, unknown>;
};


export interface InboundEvent {
  id: string;
  source_id: string;
  tenant_id: string | null;
  idempotency_key: string;
  raw_payload: Record<string, unknown>;
  case_id: string | null;
  status: InboundEventStatus;
  attempt_count: number;
  max_attempts: number;
  last_error: string | null;
  last_attempted_at: string | null;
  next_retry_at: string | null;
  received_at: string;
  processed_at: string | null;
}
