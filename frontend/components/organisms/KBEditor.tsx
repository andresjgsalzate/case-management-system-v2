"use client";

import { useEffect, useMemo, useRef } from "react";
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/ariakit";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/ariakit/style.css";
import { BlockNoteSchema, createCodeBlockSpec, type PartialBlock } from "@blocknote/core";
import type { HighlighterGeneric } from "@shikijs/types";

// Lenguajes habilitados en el slash-command `/code` y en el dropdown del bloque.
// Restringido al stack del proyecto — añadir más implica cargar más grammars de
// Shiki, que pesan ~5–10 KB cada uno (lazy-loaded en el primer code block).
const schema = BlockNoteSchema.create().extend({
  blockSpecs: {
    codeBlock: createCodeBlockSpec({
      indentLineWithTab: true,
      defaultLanguage: "typescript",
      supportedLanguages: {
        typescript: { name: "TypeScript", aliases: ["ts"] },
        tsx: { name: "TSX" },
        python: { name: "Python", aliases: ["py"] },
        bash: { name: "Bash", aliases: ["sh", "shell"] },
        sql: { name: "SQL" },
        json: { name: "JSON" },
        powershell: { name: "PowerShell", aliases: ["ps", "ps1"] },
      },
      // Highlighter Shiki construido con imports dinámicos: el bundle inicial no
      // incluye ningún grammar; se descargan al renderizar el primer codeBlock.
      // Usamos las grammars precompiladas que ya vienen como dep transitiva de
      // @blocknote/code-block para no añadir el paquete `shiki` completo (~1 MB).
      createHighlighter: async () => {
        const [{ createHighlighterCore }, { createJavaScriptRegexEngine }] = await Promise.all([
          import("@shikijs/core"),
          import("@shikijs/engine-javascript"),
        ]);
        const highlighter = await createHighlighterCore({
          themes: [import("@shikijs/themes/github-light")],
          langs: [
            import("@shikijs/langs-precompiled/typescript"),
            import("@shikijs/langs-precompiled/tsx"),
            import("@shikijs/langs-precompiled/python"),
            import("@shikijs/langs-precompiled/bash"),
            import("@shikijs/langs-precompiled/sql"),
            import("@shikijs/langs-precompiled/json"),
            import("@shikijs/langs-precompiled/powershell"),
          ],
          engine: createJavaScriptRegexEngine(),
        });
        // HighlighterCore y HighlighterGeneric<any,any> son la misma forma en
        // runtime; el cast salva el mismatch nominal entre los tipos de Shiki.
        return highlighter as unknown as HighlighterGeneric<string, string>;
      },
    }),
  },
});

interface KBEditorProps {
  /** Contenido inicial en formato BlockNote. Se espera { blocks: Block[] }. */
  initialContent?: Record<string, unknown>;
  /** Si true, el editor es solo lectura. */
  readOnly?: boolean;
  /** Callback que recibe { content_json, content_text } cuando el contenido cambia. */
  onChange?: (value: { content_json: Record<string, unknown>; content_text: string }) => void;
}

export function KBEditor({ initialContent, readOnly = false, onChange }: KBEditorProps) {
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  });

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const initialBlocks = useMemo(() => {
    const blocks = initialContent?.blocks;
    if (!blocks || !Array.isArray(blocks) || blocks.length === 0) return undefined;
    const validBlocks = (blocks as unknown[]).filter(
      (b): b is PartialBlock =>
        typeof b === "object" && b !== null && typeof (b as Record<string, unknown>).type === "string"
    );
    return validBlocks.length > 0 ? validBlocks : undefined;
  }, []); // Solo en mount — el editor es uncontrolled

  const editor = useCreateBlockNote({ schema, initialContent: initialBlocks });

  useEffect(() => {
    if (readOnly || !onChangeRef.current) return;
    const unsubscribe = editor.onChange(async (editor) => {
      const blocks = editor.document;
      const text = await editor.blocksToMarkdownLossy(blocks);
      onChangeRef.current?.({ content_json: { blocks }, content_text: text });
    });
    return () => unsubscribe();
  }, [editor, readOnly]);

  return (
    <div className="rounded-md border border-border bg-background min-h-[300px] overflow-hidden">
      <BlockNoteView editor={editor} editable={!readOnly} theme="light" />
    </div>
  );
}
