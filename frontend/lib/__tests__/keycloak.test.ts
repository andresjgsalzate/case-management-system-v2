import { describe, it, expect, beforeEach } from "vitest";

import { getUserManager, resetUserManagerForTests } from "../keycloak";

describe("keycloak UserManager", () => {
  beforeEach(() => {
    resetUserManagerForTests();
  });

  it("returns the same instance across calls (singleton)", () => {
    const first = getUserManager();
    const second = getUserManager();
    expect(first).toBe(second);
  });

  it("configures the realm authority and PKCE code flow", () => {
    const um = getUserManager();
    expect(um.settings.authority).toContain("/realms/cms");
    expect(um.settings.client_id).toBe("cms-frontend");
    expect(um.settings.response_type).toBe("code");
    expect(um.settings.scope).toContain("openid");
  });

  it("targets /auth/callback under the current origin", () => {
    const um = getUserManager();
    expect(um.settings.redirect_uri).toMatch(/\/auth\/callback$/);
  });
});
