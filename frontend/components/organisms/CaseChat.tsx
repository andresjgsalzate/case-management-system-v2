"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Pencil, Trash2, X, Check } from "lucide-react";
import { apiClient } from "@/lib/apiClient";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { formatRelative } from "@/lib/utils";

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

interface CaseChatProps {
  caseId: string;
  currentUserId: string;
}

const EDIT_WINDOW_MS = 15 * 60 * 1000; // 15 min

export function CaseChat({ caseId, currentUserId }: CaseChatProps) {
  const confirm = useConfirm();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Load history
  useEffect(() => {
    apiClient
      .get<{ data: ChatMessage[] }>(`/cases/${caseId}/chat?limit=100`)
      .then((r) => setMessages(r.data.data ?? []))
      .catch(() => {});
  }, [caseId]);

  // WebSocket for real-time
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const wsUrl = `ws://127.0.0.1:8000/api/v1/cases/${caseId}/chat/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "new_message") {
        // Reload the new message fully from REST to get all fields
        apiClient
          .get<{ data: ChatMessage[] }>(`/cases/${caseId}/chat?limit=100`)
          .then((r) => setMessages(r.data.data ?? []))
          .catch(() => {});
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
  }, [caseId]);

  // Scroll to bottom on new messages
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

  const saveEdit = useCallback(
    async (messageId: string) => {
      if (!editText.trim()) return;
      try {
        await apiClient.patch(`/cases/${caseId}/chat/${messageId}`, {
          content: editText.trim(),
        });
        setEditingId(null);
      } catch {}
    },
    [caseId, editText]
  );

  const deleteMessage = useCallback(
    async (messageId: string) => {
      const ok = await confirm({ description: "¿Eliminar este mensaje?" });
      if (!ok) return;
      try {
        await apiClient.delete(`/cases/${caseId}/chat/${messageId}`);
      } catch {}
    },
    [caseId, confirm]
  );

  const canEdit = (msg: ChatMessage) =>
    msg.user_id === currentUserId &&
    !msg.is_deleted &&
    Date.now() - new Date(msg.created_at).getTime() < EDIT_WINDOW_MS;

  return (
    <div className="flex flex-col h-[500px]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground italic text-center py-8">
            No hay mensajes todavía. ¡Sé el primero en escribir!
          </p>
        )}
        {messages.map((msg) => {
          const isOwn = msg.user_id === currentUserId;
          return (
            <div
              key={msg.id}
              className={`flex gap-2 ${isOwn ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar con iniciales del nombre real */}
              <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium shrink-0 mt-1" title={msg.sender_name}>
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

                  {/* Action buttons — only for own non-deleted messages */}
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

      {/* Input */}
      <div className="border-t border-border pt-3 mt-3 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
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
  );
}
