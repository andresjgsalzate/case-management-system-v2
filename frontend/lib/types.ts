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
}

export interface Team {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  member_count?: number;
}

// ─── Cases ────────────────────────────────────────────────────────────────────

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

export interface KBArticle {
  id: string;
  title: string;
  content_json: Record<string, unknown>;
  content_text: string;
  status: KBStatus;
  version: number;
  created_by_id: string;
  approved_by_id?: string;
  published_at?: string;
  view_count: number;
  helpful_count: number;
  not_helpful_count: number;
  created_at: string;
  updated_at: string;
  tags?: KBTag[];
  document_type_id?: string | null;
  document_type?: KBDocumentTypeRef | null;
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
  document_type: KBDocumentType | null;
  linked_at: string;
}
