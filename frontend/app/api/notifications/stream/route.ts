import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// Prevent Next.js from caching or statically optimizing this route
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const authorization = request.headers.get("authorization");
  if (!authorization) {
    return new Response("Unauthorized", { status: 401 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(
      `${BACKEND_URL}/api/v1/notifications/stream`,
      {
        headers: {
          authorization,
          accept: "text/event-stream",
          "cache-control": "no-cache",
        },
        // Do NOT pass request.signal — in React Strict Mode (dev) the incoming
        // request gets aborted on the first unmount, causing an AbortError here.
        // The backend handles cleanup via request.is_disconnected().
      }
    );
  } catch (err) {
    const isAbort = err instanceof Error && err.name === "AbortError";
    if (isAbort) {
      return new Response(null, { status: 204 });
    }
    return new Response("Backend unavailable", { status: 503 });
  }

  if (!backendResponse.ok || !backendResponse.body) {
    return new Response("Backend error", { status: backendResponse.status });
  }

  // Pipe the backend stream directly to the client without buffering
  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
      connection: "keep-alive",
    },
  });
}
