"use client";

import { useEffect, useState } from "react";
import { usePermissionGuard } from "@/hooks/usePermissionGuard";

/**
 * Embeds the n8n editor under /n8n/ via the same origin. The browser
 * session cookie set by oauth2-proxy after Keycloak login flows in
 * naturally because the iframe is same-origin.
 *
 * Hash routing: the iframe initial src mirrors the parent URL hash so
 * deep links like /n8n#/workflow/123 land directly on the workflow.
 * n8n itself does the in-iframe routing once the hash arrives.
 *
 * Permission gate: `usePermissionGuard` redirects to /cases if the user
 * lacks `n8n_editor:access`. Phase 4 swaps the redirect for a 403 page
 * with a "File a Workflow Change Request" call to action.
 *
 * Sub-spec 09 §3.7.
 */
export default function N8nEditorPage() {
  usePermissionGuard("n8n_editor", "access");

  const [iframeSrc, setIframeSrc] = useState("/n8n/");

  useEffect(() => {
    if (typeof window === "undefined") return;
    // Carry the parent hash into the iframe so deep links work.
    // `window.location.hash` already includes the leading `#`.
    const hash = window.location.hash;
    setIframeSrc(`/n8n/${hash}`);
  }, []);

  return (
    <iframe
      src={iframeSrc}
      className="w-full h-[calc(100vh-3.5rem)] border-0"
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
      title="Editor n8n"
    />
  );
}
