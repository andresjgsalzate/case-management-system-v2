"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronLeft, Clock, User, Tag, Calendar } from "lucide-react";
import { useCase } from "@/hooks/useCases";
import { StatusBadge } from "@/components/molecules/StatusBadge";
import { PriorityBadge } from "@/components/molecules/PriorityBadge";
import { Avatar } from "@/components/atoms/Avatar";
import { Spinner } from "@/components/atoms/Spinner";
import { formatDate, formatRelative } from "@/lib/utils";

type Tab = "details" | "notes" | "chat";

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const { data: c, isLoading, error } = useCase(params.id);
  const [tab, setTab] = useState<Tab>("details");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !c) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
        <p>Caso no encontrado.</p>
        <Link href="/cases" className="text-primary text-sm hover:underline">
          Volver a casos
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 max-w-4xl">
      {/* Back */}
      <Link
        href="/cases"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        Casos
      </Link>

      {/* Header card */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono text-xs text-muted-foreground">{c.case_number}</span>
              {c.status && <StatusBadge status={c.status.name} />}
              {c.priority && <PriorityBadge priority={c.priority.name} />}
            </div>
            <h1 className="text-xl font-semibold text-foreground">{c.title}</h1>
          </div>
        </div>

        {/* Meta grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 pt-5 border-t border-border">
          <MetaItem icon={User} label="Asignado a">
            {c.assigned_user ? (
              <div className="flex items-center gap-1.5">
                <Avatar name={c.assigned_user.full_name} size="xs" />
                <span className="text-sm truncate">{c.assigned_user.full_name}</span>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground italic">Sin asignar</span>
            )}
          </MetaItem>
          <MetaItem icon={Tag} label="Aplicación">
            <span className="text-sm text-muted-foreground">
              {c.application_id ?? "N/A"}
            </span>
          </MetaItem>
          <MetaItem icon={Calendar} label="Creado">
            <span className="text-sm text-muted-foreground">{formatDate(c.created_at)}</span>
          </MetaItem>
          <MetaItem icon={Clock} label="Actualizado">
            <span className="text-sm text-muted-foreground">{formatRelative(c.updated_at)}</span>
          </MetaItem>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-0">
        {(["details", "notes", "chat"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {{ details: "Detalles", notes: "Notas", chat: "Chat" }[t]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="rounded-lg border border-border bg-card p-5">
        {tab === "details" && (
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Descripción</h3>
            {c.description ? (
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                {c.description}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground italic">Sin descripción</p>
            )}
          </div>
        )}
        {tab === "notes" && (
          <p className="text-sm text-muted-foreground italic">Notas del caso (próximamente)</p>
        )}
        {tab === "chat" && (
          <p className="text-sm text-muted-foreground italic">Chat del caso (próximamente)</p>
        )}
      </div>
    </div>
  );
}

function MetaItem({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      {children}
    </div>
  );
}
