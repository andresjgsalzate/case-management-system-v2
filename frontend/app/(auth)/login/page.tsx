"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Briefcase, Loader2 } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { getUserManager } from "@/lib/keycloak";

/**
 * Hybrid SSO entry: auto-fires `signinRedirect` on mount so the user
 * doesn't pay an extra click in the happy path. If oidc-client-ts
 * throws before the browser leaves the page (misconfig, network),
 * fall back to the manual button + error so the user can retry.
 *
 * Add `?prompt=login` to the URL to skip the auto-redirect (useful
 * for debugging or when the user wants to deliberately re-enter
 * credentials).
 */
export default function LoginPage() {
  const searchParams = useSearchParams();
  const skipAuto = searchParams.get("prompt") === "login";

  const [redirecting, setRedirecting] = useState(!skipAuto);
  const [error, setError] = useState("");
  const [manualLoading, setManualLoading] = useState(false);

  async function startSignin(): Promise<void> {
    setError("");
    try {
      await getUserManager().signinRedirect();
      // Browser navigates away; this never resolves on success.
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "No se pudo iniciar el flujo de inicio de sesión.";
      setError(msg);
      setRedirecting(false);
      setManualLoading(false);
    }
  }

  useEffect(() => {
    if (skipAuto) return;
    startSignin();
    // intentionally empty deps -- run exactly once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleManual(): Promise<void> {
    setManualLoading(true);
    await startSignin();
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 rounded-xl bg-primary flex items-center justify-center mb-4 shadow-md">
            <Briefcase className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">CaseManager</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {redirecting && !error
              ? "Redirigiendo al inicio de sesión…"
              : "Autentícate con tu cuenta corporativa"}
          </p>
        </div>

        {redirecting && !error ? (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Conectando con Keycloak…</span>
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm flex flex-col gap-4">
            {error && (
              <p className="text-sm text-destructive rounded-md bg-destructive/10 px-3 py-2">
                {error}
              </p>
            )}

            <Button
              onClick={handleManual}
              className="w-full"
              loading={manualLoading}
            >
              Iniciar sesión con SSO
            </Button>

            {!error && (
              <p className="text-xs text-muted-foreground text-center">
                Serás redirigido a Keycloak para completar el inicio de sesión.
              </p>
            )}
          </div>
        )}

        <p className="text-center text-xs text-muted-foreground mt-6">
          Case Management System © 2026
        </p>
      </div>
    </div>
  );
}
