"use client";

import Link from "next/link";
import { Tag as TagIcon } from "lucide-react";
import type { KBTag } from "@/lib/types";

interface Props {
  tags: KBTag[] | undefined;
}

/**
 * Sección de tags read-only para el view del artículo KB.
 * Cada tag es un Link a /kb?tag=<slug> — al hacer clic, la lista de KB
 * queda filtrada por ese tag.
 */
export function TagsSection({ tags }: Props) {
  if (!tags || tags.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
        <TagIcon className="h-4 w-4 text-muted-foreground" />
        Tags
      </h2>
      <div className="flex flex-wrap gap-1.5">
        {tags.map((t) => (
          <Link
            key={t.id}
            href={`/kb?tag=${encodeURIComponent(t.slug)}`}
            className="inline-flex items-center rounded-md bg-primary/10 text-primary text-xs px-2 py-0.5 hover:bg-primary/20 transition-colors"
            title={`Ver todos los artículos con tag "${t.name}"`}
          >
            {t.name}
          </Link>
        ))}
      </div>
    </section>
  );
}
