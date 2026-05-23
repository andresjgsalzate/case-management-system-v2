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
    // `/sso/callback`, not `/auth/callback` -- nginx routes any /auth/*
    // path straight to Keycloak so a callback under that prefix would
    // 404 at the IdP. Anything under /sso/* falls through to Next.js.
    redirect_uri: `${origin}/sso/callback`,
    post_logout_redirect_uri: `${origin}/login`,
    response_type: "code",
    // `profile` and `email` aren't defined as separate client scopes in
    // our realm import -- Keycloak only auto-creates them on UI realm
    // creation, not via realm-export.json. The email / realm_access.roles
    // / aud claims arrive anyway through inline protocolMappers on the
    // cms-frontend client (see keycloak/realm-export.json), so requesting
    // `openid` alone is enough.
    scope: "openid",
    // No userinfo round-trip — id_token already carries email + roles.
    loadUserInfo: false,
    // Tokens land in localStorage so apiClient.ts (which reads
    // `access_token` from there) keeps working without re-wiring.
    userStore:
      typeof window !== "undefined"
        ? new WebStorageStateStore({ store: window.localStorage })
        : undefined,
    monitorSession: false,
    // Refresh the access token automatically via the refresh_token
    // grant (oidc-client-ts uses POST to Keycloak's token endpoint --
    // no iframe required because we have the refresh_token). Without
    // this, the access token (Keycloak default: 15 min) expires and
    // the apiClient 401 handler forces a full /login redirect cycle.
    automaticSilentRenew: true,
    // Fire the renewal 60s before expiry so the next API call always
    // carries a valid token even under clock skew.
    accessTokenExpiringNotificationTimeInSeconds: 60,
  };
}

let instance: UserManager | null = null;

export function getUserManager(): UserManager {
  if (!instance) {
    instance = new UserManager(buildSettings());
    // Keep localStorage `access_token` / `refresh_token` (read by
    // apiClient.ts) in sync with whatever oidc-client-ts has cached.
    // Fires on initial sign-in AND on every silent renew, so the
    // axios interceptor always reads the freshest token.
    instance.events.addUserLoaded((user) => {
      if (typeof window === "undefined") return;
      if (user.access_token) {
        window.localStorage.setItem("access_token", user.access_token);
      }
      if (user.refresh_token) {
        window.localStorage.setItem("refresh_token", user.refresh_token);
      }
    });
    // If a scheduled silent renew fails (refresh token expired, IdP
    // unreachable), fall back to a clean /login bounce. Without this
    // the user is left with a stale token and every API call 401s.
    instance.events.addSilentRenewError(() => {
      if (typeof window === "undefined") return;
      window.localStorage.removeItem("access_token");
      window.localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    });
  }
  return instance;
}

/** Reset the singleton; tests only. */
export function resetUserManagerForTests(): void {
  instance = null;
}
