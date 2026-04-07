import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { CaseForm } from "@/components/organisms/CaseForm";

export default function NewCasePage() {
  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <div>
        <Link
          href="/cases"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Volver a casos
        </Link>
        <h1 className="text-xl font-semibold text-foreground">Nuevo caso</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Completa los detalles para registrar un nuevo caso de soporte.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <CaseForm />
      </div>
    </div>
  );
}
