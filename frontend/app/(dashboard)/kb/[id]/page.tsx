"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChevronLeft, Eye, ThumbsUp, ThumbsDown,
  Calendar, Star, Pencil, ChevronDown, ChevronUp, Clock, History,
} from "lucide-react";
import {
  useKBArticle, useTransitionKBArticle, useSubmitKBFeedback,
  useToggleKBFavorite, useKBVersions,
} from "@/hooks/useKB";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { DocumentTypeBadge } from "@/components/molecules/DocumentTypeBadge";
import { Spinner } from "@/components/atoms/Spinner";
import { Button } from "@/components/atoms/Button";
import { KBEditor } from "@/components/organisms/KBEditor";
import { ReviewHistoryDrawer } from "@/components/organisms/ReviewHistoryDrawer";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth.store";
import type { KBStatus, UserPermission } from "@/lib/types";

function hasPerm(
  permissions: UserPermission[] | undefined,
  module: string,
  action: string
): boolean {
  if (!permissions) return false;
  return permissions.some((p) => p.module === module && p.action === action);
}

export default function KBArticlePage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const permissions = useAuthStore((s) => s.user?.permissions);

  const canCreate = hasPerm(permissions, "knowledge_base", "create");
  const canManage = hasPerm(permissions, "knowledge_base", "manage");

  const { data: article, isLoading, error } = useKBArticle(params.id);
  const { data: versions = [] } = useKBVersions(params.id);
  const transition = useTransitionKBArticle(params.id);
  const submitFeedback = useSubmitKBFeedback(params.id);
  const toggleFavorite = useToggleKBFavorite(params.id);

  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [showVersions, setShowVersions] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [actionError, setActionError] = useState("");

  async function handleTransition(to: KBStatus, comment?: string) {
    setActionError("");
    try {
      await transition.mutateAsync({ to_status: to, comment });
      setShowRejectModal(false);
      setRejectComment("");
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setActionError(msg || "Error al cambiar el estado.");
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
        <p>Artículo no encontrado.</p>
        <Link href="/kb" className="text-primary text-sm hover:underline">
          Volver a KB
        </Link>
      </div>
    );
  }

  const status = article.status as KBStatus;
  const isEditable = (status === "draft" || status === "rejected") && canCreate;

  return (
    <div className="flex flex-col gap-5">
      {/* Back link */}
      <Link
        href="/kb"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Base de conocimiento
      </Link>

      {/* Main card */}
      <div className="rounded-lg border border-border bg-card p-6 flex flex-col gap-4">

        {/* Header row: status + action buttons */}
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={article.status} />
            <DocumentTypeBadge type={article.document_type} size="md" />
            <span className="text-xs text-muted-foreground">Versión {article.version}</span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Favorite toggle */}
            <button
              type="button"
              onClick={() => toggleFavorite.mutate()}
              className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-muted transition-colors"
              title="Marcar como favorito"
            >
              <Star className="h-4 w-4 text-amber-400" />
            </button>

            {/* Review history drawer trigger (managers) */}
            {canManage && (
              <button
                type="button"
                onClick={() => setShowHistory(true)}
                className="h-8 w-8 flex items-center justify-center rounded-md border border-border hover:bg-muted transition-colors"
                title="Historial de revisión"
              >
                <History className="h-4 w-4 text-muted-foreground" />
              </button>
            )}

            {/* Edit button (draft or rejected) */}
            {isEditable && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => router.push(`/kb/${params.id}/edit`)}
              >
                <Pencil className="h-3.5 w-3.5 mr-1" />
                Editar
              </Button>
            )}

            {/* Send to review (draft + canCreate) */}
            {status === "draft" && canCreate && (
              <Button
                size="sm"
                onClick={() => handleTransition("in_review")}
                loading={transition.isPending}
              >
                Enviar a revisión
              </Button>
            )}

            {/* Approve (in_review + canManage) */}
            {status === "in_review" && canManage && (
              <Button
                size="sm"
                onClick={() => handleTransition("approved")}
                loading={transition.isPending}
              >
                Aprobar
              </Button>
            )}

            {/* Reject (in_review + canManage) */}
            {status === "in_review" && canManage && (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setShowRejectModal(true)}
              >
                Rechazar
              </Button>
            )}

            {/* Publish (approved + canManage) */}
            {status === "approved" && canManage && (
              <Button
                size="sm"
                onClick={() => handleTransition("published")}
                loading={transition.isPending}
              >
                Publicar
              </Button>
            )}
          </div>
        </div>

        {actionError && !showRejectModal && (
          <p className="text-sm text-destructive">{actionError}</p>
        )}

        {/* Title */}
        <h1 className="text-2xl font-bold text-foreground">{article.title}</h1>

        {/* Meta row */}
        <div className="flex items-center gap-5 text-xs text-muted-foreground pb-4 border-b border-border flex-wrap">
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {formatDate(article.updated_at)}
          </span>
          <span className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" />
            {article.view_count} vistas
          </span>
          <span className="flex items-center gap-1 text-emerald-600">
            <ThumbsUp className="h-3.5 w-3.5" />
            {article.helpful_count}
          </span>
          <span className="flex items-center gap-1 text-red-500">
            <ThumbsDown className="h-3.5 w-3.5" />
            {article.not_helpful_count}
          </span>
        </div>

        {/* Content — BlockNote read-only */}
        <KBEditor initialContent={article.content_json} readOnly />

        {/* Feedback bar */}
        <div className="flex items-center gap-3 pt-2 border-t border-border">
          <span className="text-sm text-muted-foreground">¿Te fue útil este artículo?</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => submitFeedback.mutate({ is_helpful: true })}
            loading={submitFeedback.isPending}
          >
            <ThumbsUp className="h-3.5 w-3.5 mr-1 text-emerald-600" />
            Sí
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => submitFeedback.mutate({ is_helpful: false })}
            loading={submitFeedback.isPending}
          >
            <ThumbsDown className="h-3.5 w-3.5 mr-1 text-red-500" />
            No
          </Button>
        </div>
      </div>

      {/* Version history */}
      {versions.length > 0 && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <button
            type="button"
            onClick={() => setShowVersions((v) => !v)}
            className="w-full flex items-center justify-between p-4 text-sm font-medium hover:bg-muted/50 transition-colors"
          >
            <span className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              Historial de versiones ({versions.length})
            </span>
            {showVersions
              ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
              : <ChevronDown className="h-4 w-4 text-muted-foreground" />
            }
          </button>
          {showVersions && (
            <div className="divide-y divide-border">
              {versions.map((v) => (
                <div key={v.id} className="px-4 py-3 flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      v{v.version_number} — {v.title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {v.content_text.slice(0, 120)}{v.content_text.length > 120 ? "…" : ""}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(v.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Review history drawer */}
      <ReviewHistoryDrawer
        articleId={params.id}
        open={showHistory}
        onClose={() => setShowHistory(false)}
      />

      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-card rounded-lg border border-border p-6 w-full max-w-md shadow-xl flex flex-col gap-4">
            <h2 className="text-base font-semibold">Rechazar artículo</h2>
            <p className="text-sm text-muted-foreground">
              Proporciona un comentario para que el autor pueda corregir el artículo.
            </p>
            <textarea
              value={rejectComment}
              onChange={(e) => setRejectComment(e.target.value)}
              placeholder="Motivo del rechazo…"
              rows={4}
              className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
            />
            {actionError && <p className="text-sm text-destructive">{actionError}</p>}
            <div className="flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={() => { setShowRejectModal(false); setRejectComment(""); setActionError(""); }}
              >
                Cancelar
              </Button>
              <Button
                variant="destructive"
                loading={transition.isPending}
                disabled={!rejectComment.trim()}
                onClick={() => handleTransition("draft", rejectComment)}
              >
                Confirmar rechazo
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
