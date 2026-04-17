"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Pencil, Trash2, X, Check, CheckCircle2, Star, XCircle } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { useRespondResolutionRequest } from "@/hooks/useCases";
import { Spinner } from "@/components/atoms/Spinner";
import { formatRelative } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  user_id: string;
  sender_name: string;
  content: string;
  content_type: string;
  is_deleted: boolean;
  is_edited: boolean;
  created_at: string;
}

interface ResolutionPayload {
  request_id: string;
  requested_by_name: string;
  status: "pending" | "accepted" | "rejected";
  rating: number | null;
  observation: string | null;
  responded_by_name: string | null;
  responded_at: string | null;
}

interface CaseChatProps {
  caseId: string;
  currentUserId: string;
  /** ID del creador del caso (para mostrar el formulario de respuesta al reportador). */
  createdBy?: string;
  readonly?: boolean;
}

const EDIT_WINDOW_MS = 15 * 60 * 1000;

// ── Resolution Request Card ───────────────────────────────────────────────────

function ResolutionRequestCard({
  msg,
  currentUserId,
  createdBy,
  caseId,
  onRefresh,
}: {
  msg: ChatMessage;
  currentUserId: string;
  createdBy?: string;
  caseId: string;
  onRefresh: () => void;
}) {
  const payload: ResolutionPayload = JSON.parse(msg.content);
  const isReporter = currentUserId === createdBy;
  const isPending = payload.status === "pending";
  const isAccepted = payload.status === "accepted";

  const [rating, setRating] = useState(0);
  const [observation, setObservation] = useState("");
  const [hoveredStar, setHoveredStar] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const respond = useRespondResolutionRequest(caseId);

  async function handleRespond(accepted: boolean) {
    setError(null);
    if (accepted && rating === 0) {
      setError("Debes seleccionar una calificación para aceptar");
      return;
    }
    try {
      await respond.mutateAsync({
        request_id: payload.request_id,
        accepted,
        rating: accepted ? rating : null,
        observation: observation.trim() || null,
      });
      onRefresh();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string; message?: string } } };
      setError(err?.response?.data?.detail ?? err?.response?.data?.message ?? "Error al responder");
    }
  }

  // ── Tarjeta resultado: aceptado ───────────────────────────────────────────
  if (isAccepted) {
    return (
      <div className="flex justify-center py-1">
        <div className="w-full max-w-md rounded-xl border border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-800 p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">
              Solución del caso confirmada
            </span>
          </div>
          <p className="text-xs text-muted-foreground mb-2">
            Confirmada por <strong>{payload.responded_by_name}</strong>
            {payload.responded_at && <> · {formatRelative(payload.responded_at)}</>}
          </p>
          {payload.rating && (
            <div className="flex items-center gap-1 mb-1">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star
                  key={i}
                  className={`h-4 w-4 ${i < payload.rating! ? "fill-amber-400 text-amber-400" : "text-muted-foreground/30"}`}
                />
              ))}
              <span className="text-xs text-muted-foreground ml-1">{payload.rating}/5</span>
            </div>
          )}
          {payload.observation && (
            <p className="text-sm text-foreground italic mt-1">"{payload.observation}"</p>
          )}
          <p className="text-xs text-muted-foreground mt-2">
            Solución propuesta por <strong>{payload.requested_by_name}</strong>
          </p>
        </div>
      </div>
    );
  }

  // ── Tarjeta resultado: rechazado ──────────────────────────────────────────
  if (payload.status === "rejected") {
    return (
      <div className="flex justify-center py-1">
        <div className="w-full max-w-md rounded-xl border border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-800 p-4">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="h-4 w-4 text-red-600" />
            <span className="text-sm font-semibold text-red-800 dark:text-red-300">
              Solución del caso rechazada
            </span>
          </div>
          <p className="text-xs text-muted-foreground mb-1">
            Rechazada por <strong>{payload.responded_by_name}</strong>
            {payload.responded_at && <> · {formatRelative(payload.responded_at)}</>}
          </p>
          {payload.observation && (
            <p className="text-sm text-foreground italic mt-1">"{payload.observation}"</p>
          )}
          <p className="text-xs text-muted-foreground mt-2">
            El agente <strong>{payload.requested_by_name}</strong> deberá continuar trabajando en el caso.
          </p>
        </div>
      </div>
    );
  }

  // ── Tarjeta pendiente: vista del reportador ───────────────────────────────
  if (isPending && isReporter) {
    return (
      <div className="flex justify-center py-1">
        <div className="w-full max-w-md rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-4">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-800 dark:text-blue-300">
              ¿El problema fue resuelto?
            </span>
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            <strong>{payload.requested_by_name}</strong> indica que el caso está resuelto.
            Por favor confirma si la solución fue satisfactoria.
          </p>

          {/* Calificación */}
          <div className="mb-3">
            <p className="text-xs font-medium text-foreground mb-1.5">Calificación <span className="text-destructive">*</span></p>
            <div className="flex items-center gap-1">
              {Array.from({ length: 5 }).map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onMouseEnter={() => setHoveredStar(i + 1)}
                  onMouseLeave={() => setHoveredStar(0)}
                  onClick={() => setRating(i + 1)}
                  className="focus:outline-none"
                >
                  <Star
                    className={`h-6 w-6 transition-colors ${
                      i < (hoveredStar || rating)
                        ? "fill-amber-400 text-amber-400"
                        : "text-muted-foreground/30 hover:text-amber-300"
                    }`}
                  />
                </button>
              ))}
              {rating > 0 && (
                <span className="text-xs text-muted-foreground ml-2">{rating}/5</span>
              )}
            </div>
          </div>

          {/* Observación opcional */}
          <div className="mb-4">
            <p className="text-xs font-medium text-foreground mb-1.5">Observación <span className="text-muted-foreground">(opcional)</span></p>
            <textarea
              rows={2}
              value={observation}
              onChange={(e) => setObservation(e.target.value)}
              placeholder="¿Algún comentario sobre la solución?"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            />
          </div>

          {error && (
            <p className="text-xs text-destructive mb-3">{error}</p>
          )}

          {/* Botones */}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={respond.isPending}
              onClick={() => handleRespond(true)}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {respond.isPending ? <Spinner size="sm" /> : <Check className="h-3.5 w-3.5" />}
              Sí, fue resuelto
            </button>
            <button
              type="button"
              disabled={respond.isPending}
              onClick={() => handleRespond(false)}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
              No, continuar
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Tarjeta pendiente: vista del agente u otros ───────────────────────────
  return (
    <div className="flex justify-center py-1">
      <div className="w-full max-w-md rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-amber-600 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
              Confirmación de solución pendiente
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Esperando que el solicitante confirme si el caso fue resuelto · {formatRelative(msg.created_at)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── CaseChat ──────────────────────────────────────────────────────────────────

export function CaseChat({
  caseId,
  currentUserId,
  createdBy,
  readonly = false,
}: CaseChatProps) {
  const confirm = useConfirm();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const loadMessages = useCallback(() => {
    apiClient
      .get<{ data: ChatMessage[] }>(`/cases/${caseId}/chat?limit=100`)
      .then((r) => setMessages(r.data.data ?? []))
      .catch(() => {});
  }, [caseId]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const wsUrl = `ws://127.0.0.1:8000/api/v1/cases/${caseId}/chat/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "new_message") {
        loadMessages();
      } else if (msg.type === "message_edited") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msg.data.message_id
              ? { ...m, content: msg.data.content, is_edited: true }
              : m
          )
        );
      } else if (msg.type === "message_deleted") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msg.data.message_id
              ? { ...m, content: "Mensaje eliminado", is_deleted: true }
              : m
          )
        );
      }
    };

    ws.onerror = () => {};
    return () => ws.close();
  }, [caseId, loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true);
    try {
      await apiClient.post(`/cases/${caseId}/chat`, { content });
      setText("");
    } finally {
      setSending(false);
    }
  }, [caseId, text, sending]);

  const saveEdit = useCallback(async (messageId: string) => {
    if (!editText.trim()) return;
    try {
      await apiClient.patch(`/cases/${caseId}/chat/${messageId}`, { content: editText.trim() });
      setEditingId(null);
    } catch {}
  }, [caseId, editText]);

  const deleteMessage = useCallback(async (messageId: string) => {
    const ok = await confirm({ description: "¿Eliminar este mensaje?" });
    if (!ok) return;
    try { await apiClient.delete(`/cases/${caseId}/chat/${messageId}`); } catch {}
  }, [caseId, confirm]);

  const canEdit = (msg: ChatMessage) =>
    msg.user_id === currentUserId &&
    !msg.is_deleted &&
    Date.now() - new Date(msg.created_at).getTime() < EDIT_WINDOW_MS;

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground italic text-center py-8">
            No hay mensajes todavía. ¡Sé el primero en escribir!
          </p>
        )}
        {messages.map((msg) => {
          // Sistema
          if (msg.content_type === "system") {
            return (
              <div key={msg.id} className="flex justify-center py-1">
                <div className="flex items-start gap-2 max-w-[90%] rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950/20 dark:border-amber-800 px-3 py-2">
                  <span className="text-amber-500 mt-0.5 shrink-0 text-sm">📋</span>
                  <div>
                    <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
                      {msg.content.replace(/^📋\s*/, "")}
                    </p>
                    <p className="text-[10px] text-amber-600/70 dark:text-amber-500/60 mt-0.5">
                      {formatRelative(msg.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            );
          }

          // Solicitud de resolución
          if (msg.content_type === "resolution_request") {
            return (
              <ResolutionRequestCard
                key={msg.id}
                msg={msg}
                currentUserId={currentUserId}
                createdBy={createdBy}
                caseId={caseId}
                onRefresh={loadMessages}
              />
            );
          }

          // Mensaje normal
          const isOwn = msg.user_id === currentUserId;
          return (
            <div key={msg.id} className={`flex gap-2 ${isOwn ? "flex-row-reverse" : "flex-row"}`}>
              <div
                className="h-7 w-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium shrink-0 mt-1"
                title={msg.sender_name}
              >
                {msg.sender_name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()}
              </div>

              <div className={`max-w-[70%] group relative ${isOwn ? "items-end" : "items-start"} flex flex-col`}>
                {!isOwn && (
                  <span className="text-[11px] text-muted-foreground mb-0.5 px-1">{msg.sender_name}</span>
                )}
                {editingId === msg.id ? (
                  <div className="flex gap-1 items-center w-full">
                    <input
                      autoFocus
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveEdit(msg.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    <button onClick={() => saveEdit(msg.id)} className="text-primary hover:opacity-80">
                      <Check className="h-4 w-4" />
                    </button>
                    <button onClick={() => setEditingId(null)} className="text-muted-foreground hover:opacity-80">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <div
                    className={`rounded-2xl px-3 py-2 text-sm ${
                      msg.is_deleted
                        ? "bg-muted text-muted-foreground italic"
                        : isOwn
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    }`}
                  >
                    {msg.content}
                  </div>
                )}

                <div className="flex items-center gap-1.5 mt-0.5 px-1">
                  <span className="text-[11px] text-muted-foreground">
                    {formatRelative(msg.created_at)}
                    {msg.is_edited && !msg.is_deleted && (
                      <span className="ml-1 opacity-60">(editado)</span>
                    )}
                  </span>
                  {canEdit(msg) && editingId !== msg.id && (
                    <span className="hidden group-hover:flex gap-1">
                      <button
                        onClick={() => { setEditingId(msg.id); setEditText(msg.content); }}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                      <button
                        onClick={() => deleteMessage(msg.id)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      {!readonly && (
        <div className="border-t border-border pt-3 mt-3 flex flex-col gap-2">
          <div className="flex gap-2">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
              }}
              placeholder="Escribe un mensaje…"
              disabled={sending}
              className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={!text.trim() || sending}
              className="rounded-md bg-primary px-3 py-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
