"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import { getUserManager } from "@/lib/keycloak";
import { useAuthStore } from "@/store/auth.store";

/**
 * Receives the authorization code from Keycloak and finishes the PKCE
 * exchange via oidc-client-ts. The resulting access + refresh tokens
 * land in the Zustand store; localStorage keys are populated for the
 * existing apiClient interceptor without changes to that layer.
 *
 * Sub-spec 09 §3.6.
 */

// Module-level one-shot guard: React 18 + Next.js StrictMode fires the
// callback effect twice in dev. The first call consumes the
// authorization code at Keycloak's token endpoint; the second sees
// "code already used" and Keycloak returns 400. The flag survives
// StrictMode's synthetic unmount/remount and is reset on full reload.
let callbackProcessed = false;

export default function AuthCallbackPage() {
  const router = useRouter();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (callbackProcessed) return;
    callbackProcessed = true;

    (async () => {
      try {
        const user = await getUserManager().signinRedirectCallback();
        if (!user.access_token) {
          throw new Error("Keycloak no devolvió un access token.");
        }
        setTokens(user.access_token, user.refresh_token ?? "");
        localStorage.setItem("access_token", user.access_token);
        if (user.refresh_token) {
          localStorage.setItem("refresh_token", user.refresh_token);
        }
        // `state` carries the original path if the user was bounced from
        // a protected route; default to /cases when absent.
        const next = typeof user.state === "string" ? user.state : "/cases";
        router.replace(next.startsWith("/") ? next : "/cases");
      } catch (err) {
        // Release the guard so the user can retry from /login.
        callbackProcessed = false;
        setError(
          err instanceof Error
            ? err.message
            : "No se pudo completar el inicio de sesión."
        );
      }
    })();
    // intentionally empty deps -- run once per mount, gated by module flag
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-sm w-full rounded-xl border border-border bg-card p-6 shadow-sm flex flex-col items-center gap-4">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p className="text-sm text-destructive text-center">{error}</p>
          <Button onClick={() => router.replace("/login")}>
            Volver a iniciar sesión
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="flex items-center gap-3 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Completando inicio de sesión…</span>
      </div>
    </div>
  );
}
