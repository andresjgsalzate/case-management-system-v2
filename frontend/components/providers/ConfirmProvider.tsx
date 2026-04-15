"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { createContext, useCallback, useContext, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/atoms/Button";

// ── Tipos ──────────────────────────────────────────────────────────────────────
interface ConfirmOptions {
  title?: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "destructive" | "default";
}

type ConfirmFn = (options: ConfirmOptions | string) => Promise<boolean>;

// ── Contexto ───────────────────────────────────────────────────────────────────
const ConfirmContext = createContext<ConfirmFn>(() => Promise.resolve(false));

// ── Hook público ───────────────────────────────────────────────────────────────
export function useConfirm(): ConfirmFn {
  return useContext(ConfirmContext);
}

// ── Provider ───────────────────────────────────────────────────────────────────
export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<Required<ConfirmOptions>>({
    title: "¿Confirmar acción?",
    description: "",
    confirmLabel: "Confirmar",
    cancelLabel: "Cancelar",
    variant: "destructive",
  });

  // Guardamos resolve de la promesa activa
  const resolveRef = useRef<(value: boolean) => void>(() => {});

  const confirm: ConfirmFn = useCallback((input) => {
    const opts: ConfirmOptions =
      typeof input === "string" ? { description: input } : input;

    setOptions({
      title: opts.title ?? "¿Confirmar acción?",
      description: opts.description,
      confirmLabel: opts.confirmLabel ?? (opts.variant === "destructive" ? "Eliminar" : "Confirmar"),
      cancelLabel: opts.cancelLabel ?? "Cancelar",
      variant: opts.variant ?? "destructive",
    });
    setOpen(true);

    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  function handleConfirm() {
    setOpen(false);
    resolveRef.current(true);
  }

  function handleCancel() {
    setOpen(false);
    resolveRef.current(false);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}

      <Dialog.Root open={open} onOpenChange={(v) => { if (!v) handleCancel(); }}>
        <Dialog.Portal>
          {/* Overlay */}
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />

          {/* Panel */}
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card shadow-xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=open]:slide-in-from-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-top-[48%]">
            <div className="flex flex-col gap-4 p-6">
              {/* Ícono + título */}
              <div className="flex items-start gap-3">
                {options.variant === "destructive" && (
                  <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
                    <AlertTriangle className="h-4.5 w-4.5 text-destructive" />
                  </div>
                )}
                <div>
                  <Dialog.Title className="text-sm font-semibold text-foreground">
                    {options.title}
                  </Dialog.Title>
                  <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                    {options.description}
                  </Dialog.Description>
                </div>
              </div>

              {/* Acciones */}
              <div className="flex justify-end gap-2 pt-1">
                <Button variant="outline" size="sm" onClick={handleCancel}>
                  {options.cancelLabel}
                </Button>
                <Button
                  variant={options.variant === "destructive" ? "destructive" : "default"}
                  size="sm"
                  onClick={handleConfirm}
                >
                  {options.confirmLabel}
                </Button>
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </ConfirmContext.Provider>
  );
}
