"use client";

import { useRef, useState } from "react";
import {
  Paperclip, Upload, Trash2, Download,
  FileText, FileImage, FileVideo, FileAudio, FileArchive, File,
} from "lucide-react";
import {
  useAttachments,
  useUploadAttachment,
  useDeleteAttachment,
  downloadAttachment,
} from "@/hooks/useCases";
import { useHasPermission } from "@/hooks/useHasPermission";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate } from "@/lib/utils";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileIcon({ mimeType }: { mimeType: string }) {
  if (mimeType.startsWith("image/"))       return <FileImage  className="h-4 w-4 text-blue-500"   />;
  if (mimeType.startsWith("video/"))       return <FileVideo  className="h-4 w-4 text-violet-500" />;
  if (mimeType.startsWith("audio/"))       return <FileAudio  className="h-4 w-4 text-pink-500"   />;
  if (mimeType === "application/pdf")      return <FileText   className="h-4 w-4 text-red-500"    />;
  if (mimeType.includes("zip") || mimeType.includes("tar") || mimeType.includes("compressed"))
                                           return <FileArchive className="h-4 w-4 text-amber-500" />;
  if (mimeType.startsWith("text/"))        return <FileText   className="h-4 w-4 text-slate-500"  />;
  return                                          <File       className="h-4 w-4 text-slate-400"  />;
}

interface CaseAttachmentsProps {
  caseId: string;
  readonly?: boolean;
}

export function CaseAttachments({ caseId, readonly }: CaseAttachmentsProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const canCreate = useHasPermission("attachments", "create");
  const canDelete = useHasPermission("attachments", "delete");

  const { data: attachments = [], isLoading } = useAttachments(caseId);
  const upload = useUploadAttachment(caseId);
  const remove = useDeleteAttachment(caseId);

  const showUpload = canCreate && !readonly;

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    for (const file of Array.from(files)) {
      await upload.mutateAsync(file);
    }
  }

  async function handleDownload(attachmentId: string, filename: string) {
    setDownloadingId(attachmentId);
    try {
      await downloadAttachment(caseId, attachmentId, filename);
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(attachmentId: string) {
    await remove.mutateAsync(attachmentId);
    setDeleteConfirm(null);
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <Paperclip className="h-4 w-4" />
          Archivos adjuntos
          {attachments.length > 0 && (
            <span className="text-xs text-muted-foreground/70">({attachments.length})</span>
          )}
        </div>
        {showUpload && (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={upload.isPending}
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
          >
            {upload.isPending ? <Spinner size="sm" /> : <Upload className="h-3.5 w-3.5" />}
            Adjuntar
          </button>
        )}
      </div>

      {/* Upload error */}
      {upload.isError && (
        <p className="text-xs text-destructive">
          {(upload.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Error al subir el archivo"}
        </p>
      )}

      {/* Drop zone (only when upload is allowed) */}
      {showUpload && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
          className={`rounded-lg border-2 border-dashed px-4 py-5 text-center text-xs text-muted-foreground transition-colors cursor-pointer ${
            dragOver
              ? "border-primary/60 bg-primary/5"
              : "border-border hover:border-muted-foreground/40 hover:bg-muted/30"
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          {upload.isPending
            ? "Subiendo…"
            : "Arrastra archivos aquí o haz clic para seleccionar"}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {/* Empty state */}
      {attachments.length === 0 && (
        <p className="text-xs text-muted-foreground italic py-2">
          Sin archivos adjuntos
        </p>
      )}

      {/* File list — scroll independiente cuando hay muchos adjuntos */}
      {attachments.length > 0 && (
        <ul className="flex flex-col divide-y divide-border rounded-lg border border-border overflow-hidden overflow-y-auto max-h-52">
          {attachments.map((att) => (
            <li key={att.id} className="flex items-center gap-3 px-3 py-2.5 bg-card hover:bg-muted/30 transition-colors group">
              <FileIcon mimeType={att.mime_type} />

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{att.original_filename}</p>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(att.file_size)} · {formatDate(att.created_at)}
                </p>
              </div>

              <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                {/* Download */}
                <button
                  type="button"
                  title="Descargar"
                  disabled={downloadingId === att.id}
                  onClick={() => handleDownload(att.id, att.original_filename)}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
                >
                  {downloadingId === att.id ? <Spinner size="sm" /> : <Download className="h-3.5 w-3.5" />}
                </button>

                {/* Delete */}
                {canDelete && !readonly && (
                  deleteConfirm === att.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => handleDelete(att.id)}
                        disabled={remove.isPending}
                        className="px-2 py-0.5 rounded text-xs bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
                      >
                        Eliminar
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteConfirm(null)}
                        className="px-2 py-0.5 rounded text-xs border border-border bg-background hover:bg-muted transition-colors"
                      >
                        Cancelar
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      title="Eliminar"
                      onClick={() => setDeleteConfirm(att.id)}
                      className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
