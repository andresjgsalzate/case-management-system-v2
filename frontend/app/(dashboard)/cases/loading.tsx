/**
 * Skeleton específico de /cases.
 *
 * Estrategia: el header, las tabs y los filtros se renderizan IDÉNTICOS a la
 * página real (texto estático) para dar continuidad visual durante la
 * navegación. Solo el área de tabla muestra "shimmer rows".
 *
 * Nota: esto no es un componente client, no usa hooks — es puro JSX estático
 * que Next renderiza instantáneamente como fallback de <Suspense>.
 */
export default function CasesLoading() {
  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Casos</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Cargando…</p>
        </div>
        <div className="h-8 w-28 rounded-md bg-muted animate-pulse" />
      </div>

      {/* Queue tabs placeholder */}
      <div className="flex items-center gap-1 border-b border-border">
        {["Mi cola", "Equipo", "Todos"].map((label) => (
          <div
            key={label}
            className="px-4 py-2 text-sm font-medium -mb-px border-b-2 border-transparent text-muted-foreground"
          >
            {label}
          </div>
        ))}
      </div>

      {/* Filters row placeholder */}
      <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
        <div className="h-9 w-64 rounded-md bg-muted animate-pulse" />
        <div className="h-9 w-72 rounded-md bg-muted animate-pulse" />
        <div className="h-8 w-40 rounded-md bg-muted animate-pulse" />
      </div>

      {/* Table skeleton — header real + 8 filas con shimmer */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {["Caso", "Título", "Estado", "Prioridad", "Asignado a", "Creado"].map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
              <th className="px-4 py-3 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {Array.from({ length: 8 }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-3">
                  <div className="h-4 w-20 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-48 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-5 w-16 rounded-full bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3">
                  <div className="h-5 w-16 rounded-full bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="h-5 w-5 rounded-full bg-muted animate-pulse" />
                    <div className="h-4 w-24 rounded bg-muted animate-pulse" />
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="h-4 w-24 rounded bg-muted animate-pulse" />
                </td>
                <td className="px-4 py-3" />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
