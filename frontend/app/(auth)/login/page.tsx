"use client";

import { useState } from "react";
import { Briefcase } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { getUserManager } from "@/lib/keycloak";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin() {
    setError("");
    setLoading(true);
    try {
      await getUserManager().signinRedirect();
      // We never come back here -- signinRedirect navigates away.
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar el flujo de inicio de sesión.");
      setLoading(false);
    }
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
            Autentícate con tu cuenta corporativa
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-sm flex flex-col gap-4">
          {error && (
            <p className="text-sm text-destructive rounded-md bg-destructive/10 px-3 py-2">
              {error}
            </p>
          )}

          <Button onClick={handleLogin} className="w-full" loading={loading}>
            Iniciar sesión con SSO
          </Button>

          <p className="text-xs text-muted-foreground text-center">
            Serás redirigido a Keycloak para completar el inicio de sesión.
          </p>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Case Management System © 2026
        </p>
      </div>
    </div>
  );
}
