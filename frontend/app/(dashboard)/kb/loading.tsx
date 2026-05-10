export default function KBLoading() {
  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Base de Conocimiento</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Cargando…</p>
        </div>
        <div className="h-8 w-32 rounded-md bg-muted animate-pulse" />
      </div>

      {/* Search + status tabs placeholder */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="h-9 w-72 rounded-md bg-muted animate-pulse" />
        <div className="flex items-center gap-1 overflow-x-auto">
          {["Todos", "Publicados", "En revisión", "Borradores", "Rechazados"].map((label) => (
            <div
              key={label}
              className="px-3 py-1.5 rounded-md text-sm whitespace-nowrap text-muted-foreground"
            >
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Cards skeleton — 6 cards con shimmer */}
      <div className="grid gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border border-border bg-card p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                {/* Badges row */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <div className="h-5 w-16 rounded-full bg-muted animate-pulse" />
                  <div className="h-5 w-20 rounded-full bg-muted animate-pulse" />
                  <div className="h-3 w-8 rounded bg-muted animate-pulse" />
                </div>
                {/* Title */}
                <div className="h-4 w-3/5 rounded bg-muted animate-pulse" />
                {/* Description — dos líneas */}
                <div className="mt-2 space-y-1.5">
                  <div className="h-3 w-full rounded bg-muted animate-pulse" />
                  <div className="h-3 w-4/5 rounded bg-muted animate-pulse" />
                </div>
              </div>
            </div>
            {/* Stats row */}
            <div className="flex items-center gap-4 mt-3">
              <div className="h-3 w-10 rounded bg-muted animate-pulse" />
              <div className="h-3 w-10 rounded bg-muted animate-pulse" />
              <div className="h-3 w-20 rounded bg-muted animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
