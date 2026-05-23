import axios, { AxiosInstance, AxiosRequestConfig } from "axios";

import { getUserManager } from "@/lib/keycloak";

// nginx terminates TLS at cms.local:443 and routes /api/* directly to
// the backend (FastAPI), so the browser can target /api/v1/* without
// going through the legacy Next.js proxy under /api/proxy. The proxy
// route stays in the repo for now -- only reachable when the frontend
// is hit directly on port 3000 (no nginx) -- but isn't on the hot path.
const BASE_URL =
  typeof window !== "undefined"
    ? "/api/v1"
    : `${process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000"}/api/v1`;

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function setAccessToken(token: string): void {
  localStorage.setItem("access_token", token);
}

function clearTokens(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function getCurrentUserId(): string | null {
  const token = getAccessToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.sub ?? null;
  } catch {
    return null;
  }
}

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token!);
    }
  });
  failedQueue = [];
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Request interceptor: attach access token
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: auto-refresh on 401
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & {
      _retry?: boolean;
    };

    if (error.response?.status !== 401 || originalRequest._retry) {
      // Surface the server-side message so React Query callers see
      // "tuic_code 'X' already exists" instead of the generic
      // "Request failed with status code 400". Three known shapes:
      //   - App envelope:  { success: false, error, message }   <- ours
      //   - FastAPI HTTPException: { detail: "..." }
      //   - Pydantic 422:  { detail: [{loc, msg, type}, ...] }
      const data = error.response?.data;
      const fromAppEnvelope =
        data && typeof data === "object" && typeof data.message === "string"
          ? data.message
          : null;
      const detail = data?.detail;
      const fromDetail =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .map((e: { msg?: string; loc?: unknown[] }) =>
                  e.loc ? `${e.loc.join(".")}: ${e.msg}` : e.msg,
                )
                .filter(Boolean)
                .join("; ")
            : null;
      const better = fromAppEnvelope ?? fromDetail;
      if (better) error.message = better;
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers = {
          ...originalRequest.headers,
          Authorization: `Bearer ${token}`,
        };
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    // Ask oidc-client-ts to refresh via Keycloak's token endpoint
    // (uses the refresh_token grant, no iframe). The userManager's
    // `addUserLoaded` handler mirrors the new tokens to localStorage.
    // If the scheduled silent renew already ran in the background,
    // signinSilent is a near no-op and resolves quickly.
    try {
      const um = getUserManager();
      const user = await um.signinSilent();
      const newToken = user?.access_token;
      if (!newToken) {
        throw new Error("signinSilent returned no access_token");
      }
      setAccessToken(newToken);
      processQueue(null, newToken);
      originalRequest.headers = {
        ...originalRequest.headers,
        Authorization: `Bearer ${newToken}`,
      };
      return apiClient(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      clearTokens();
      // Best-effort clear of oidc-client-ts's own store too, so the
      // next /login auto-redirect starts from a clean slate.
      try {
        await getUserManager().removeUser();
      } catch {
        // ignore -- we're already on the failure path
      }
      window.location.href = "/login";
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);
