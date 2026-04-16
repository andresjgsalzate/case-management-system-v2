"use client";

import { useEffect, useMemo } from "react";
import { useCreateBlockNote, BlockNoteViewRaw } from "@blocknote/react";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/react/style.css";
import type { PartialBlock } from "@blocknote/core";

interface KBEditorProps {
  /** Contenido inicial en formato BlockNote. Se espera { blocks: Block[] }. */
  initialContent?: Record<string, unknown>;
  /** Si true, el editor es solo lectura. */
  readOnly?: boolean;
  /** Callback que recibe { content_json, content_text } cuando el contenido cambia. */
  onChange?: (value: { content_json: Record<string, unknown>; content_text: string }) => void;
}

export function KBEditor({ initialContent, readOnly = false, onChange }: KBEditorProps) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const initialBlocks = useMemo(() => {
    const blocks = initialContent?.blocks;
    if (!blocks || !Array.isArray(blocks) || blocks.length === 0) return undefined;
    return blocks as PartialBlock[];
  }, []); // Solo en mount — el editor es uncontrolled

  const editor = useCreateBlockNote({ initialContent: initialBlocks });

  useEffect(() => {
    if (readOnly || !onChange) return;
    const unsubscribe = editor.onChange(async () => {
      const blocks = editor.document;
      const text = await editor.blocksToMarkdownLossy(blocks);
      onChange({ content_json: { blocks }, content_text: text });
    });
    return () => unsubscribe();
  }, [editor, onChange, readOnly]);

  return (
    <div className="rounded-md border border-border bg-background min-h-[300px] overflow-hidden">
      <BlockNoteViewRaw editor={editor} editable={!readOnly} theme="light" />
    </div>
  );
}
