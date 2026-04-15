"use client";

import { useState } from "react";
import { Pencil, Trash2, X, Check, StickyNote } from "lucide-react";
import { useCaseNotes, useCreateNote, useUpdateNote, useDeleteNote } from "@/hooks/useCases";
import { useConfirm } from "@/components/providers/ConfirmProvider";
import { getCurrentUserId } from "@/lib/apiClient";
import { formatRelative } from "@/lib/utils";

interface CaseNotesProps {
  caseId: string;
}

export function CaseNotes({ caseId }: CaseNotesProps) {
  const confirm = useConfirm();
  const currentUserId = getCurrentUserId();
  const { data: notes = [], isLoading } = useCaseNotes(caseId);
  const createNote = useCreateNote(caseId);
  const updateNote = useUpdateNote(caseId);
  const deleteNote = useDeleteNote(caseId);

  const [newContent, setNewContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  async function handleCreate() {
    if (!newContent.trim()) return;
    await createNote.mutateAsync(newContent.trim());
    setNewContent("");
  }

  async function handleUpdate(noteId: string) {
    if (!editContent.trim()) return;
    await updateNote.mutateAsync({ noteId, content: editContent.trim() });
    setEditingId(null);
  }

  async function handleDelete(noteId: string) {
    const ok = await confirm({ description: "¿Eliminar esta nota?" });
    if (!ok) return;
    await deleteNote.mutateAsync(noteId);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Add note */}
      <div className="flex flex-col gap-2">
        <textarea
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          placeholder="Escribe una nota interna…"
          rows={3}
          className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
        />
        <div className="flex justify-end">
          <button
            onClick={handleCreate}
            disabled={!newContent.trim() || createNote.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <StickyNote className="h-3.5 w-3.5" />
            Agregar nota
          </button>
        </div>
      </div>

      {/* Notes list */}
      {isLoading ? (
        <p className="text-sm text-muted-foreground text-center py-4">Cargando notas…</p>
      ) : notes.length === 0 ? (
        <p className="text-sm text-muted-foreground italic text-center py-4">Sin notas todavía.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {notes.map((note) => (
            <div key={note.id} className="rounded-md border border-border bg-muted/30 p-3 group">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-foreground">{note.sender_name}</span>
                  <span className="text-[11px] text-muted-foreground">{formatRelative(note.created_at)}</span>
                </div>
                {note.user_id === currentUserId && (
                  <div className="hidden group-hover:flex gap-1">
                    <button
                      onClick={() => { setEditingId(note.id); setEditContent(note.content); }}
                      className="text-muted-foreground hover:text-foreground p-0.5"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(note.id)}
                      className="text-muted-foreground hover:text-destructive p-0.5"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>

              {editingId === note.id ? (
                <div className="flex flex-col gap-2">
                  <textarea
                    autoFocus
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={2}
                    className="flex w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                  />
                  <div className="flex justify-end gap-1">
                    <button onClick={() => setEditingId(null)} className="text-muted-foreground hover:text-foreground">
                      <X className="h-4 w-4" />
                    </button>
                    <button onClick={() => handleUpdate(note.id)} className="text-primary hover:opacity-80">
                      <Check className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{note.content}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
