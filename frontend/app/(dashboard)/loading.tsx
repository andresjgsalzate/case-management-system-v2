import { Spinner } from "@/components/atoms/Spinner";

export default function DashboardLoading() {
  return (
    <div className="flex h-full w-full items-center justify-center py-24">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <Spinner size="lg" />
        <p className="text-sm">Cargando…</p>
      </div>
    </div>
  );
}
