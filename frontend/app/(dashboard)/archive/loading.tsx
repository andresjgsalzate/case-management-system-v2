export default function ArchiveLoading() {
  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-muted animate-pulse" />
          <div>
            <h1 className="text-xl font-semibold text-foreground">Archivo</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Cargando…</p>
          </div>
        </div>
      </div>

      {/* Search placeholder */}
      <div className="flex items-center gap-3">
        <div className="h-9 w-72 rounded-md bg-muted animate-pulse" />
      </div>

      {/* Table skeleton — header real + 8 filas con shimmer */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">Número</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Título</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32 hidden sm:table-cell">Estado</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28 hidden md:table-cell">Prioridad</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32 hidden lg:table-cell">Cerrado</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32 hidden lg:table-cell">Archivado</th>
              <th className="text-right px-4 py-3 w-36" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {Array.from({ length: 8 }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-3">
                  <div className="h-5 w-20 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-48 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3 hidden sm:table-cell">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-muted animate-pulse" />
                    <div className="h-3 w-16 rounded bg-muted animate-pulse" />
                  </div>
                </td>
                <td className="px-4 py-3 hidden md:table-cell">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-muted animate-pulse" />
                    <div className="h-3 w-14 rounded bg-muted animate-pulse" />
                  </div>
                </td>
                <td className="px-4 py-3 hidden lg:table-cell">
                  <div className="h-3 w-20 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3 hidden lg:table-cell">
                  <div className="h-3 w-20 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="h-7 w-24 rounded-md bg-muted animate-pulse ml-auto" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
