/**
 * Browser-side OIDC client (sub-spec 09 §3.6).
 *
 * Drives the Authorization Code + PKCE flow against the Keycloak realm
 * exposed at https://cms.local/auth/realms/cms. The same origin
 * (`cms.local`) hosts both the SPA and Keycloak, so the post-login
 * session cookie set by Keycloak naturally flows into the n8n iframe
 * loaded under /n8n/ — no SameSite=None gymnastics.
 *
 * Singleton on purpose: oidc-client-ts caches its state machine and
 * silent-renew iframes inside the instance, and we want one source of
 * truth across the app.
 */

import { UserManager, type UserManagerSettings, WebStorageStateStore } from "oidc-client-ts";

const DEFAULT_AUTHORITY = "https://cms.local/auth/realms/cms";
const DEFAULT_CLIENT_ID = "cms-frontend";

function buildSettings(): UserManagerSettings {
  const authority =
    process.env.NEXT_PUBLIC_KEYCLOAK_AUTHORITY ?? DEFAULT_AUTHORITY;
  const clientId =
    process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? DEFAULT_CLIENT_ID;

  // window.location is only available in the browser. The SSR fallback
  // uses the dev origin; Next.js never actually invokes signinRedirect
  // server-side, so this only matters for module load order.
  const origin =
    typeof window !== "undefined" ? window.location.origin : "https://cms.local";

  return {
    authority,
    client_id: clientId,
    redirect_uri: `${origin}/auth/callback`,
    post_logout_redirect_uri: `${origin}/login`,
    response_type: "code",
    scope: "openid profile email",
    // No userinfo round-trip — id_token already carries email + roles.
    loadUserInfo: false,
    // Tokens land in localStorage so apiClient.ts (which reads
    // `access_token` from there) keeps working without re-wiring.
    userStore:
      typeof window !== "undefined"
        ? new WebStorageStateStore({ store: window.localStorage })
        : undefined,
    // Disable monitorSession + automaticSilentRenew for now — silent
    // renewal lands in a follow-up; the SPA falls back to re-login when
    // the access token expires.
    monitorSession: false,
    automaticSilentRenew: false,
  };
}

let instance: UserManager | null = null;

export function getUserManager(): UserManager {
  if (!instance) {
    instance = new UserManager(buildSettings());
  }
  return instance;
}

/** Reset the singleton; tests only. */
export function resetUserManagerForTests(): void {
  instance = null;
}
