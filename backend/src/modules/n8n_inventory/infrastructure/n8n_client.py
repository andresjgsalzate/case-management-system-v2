"""Thin wrapper around n8n's Public REST API.

Auth is a single header (`X-N8N-API-KEY`) -- the key is generated in
n8n's UI by the owner account. n8n Community 1.65 exposes the API at
`/api/v1/...` regardless of N8N_PATH; the URL we reach it at depends
on the deployment (in-docker -> `http://n8n:5678/api/v1`; dev with
backend on host -> through nginx's `/n8n-api/` prefix-stripper).
"""

from __future__ import annotations

from typing import Any

import httpx


class N8nApiClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = http_client
        self._owns_http = http_client is None
        self._verify_ssl = verify_ssl

    async def list_workflows(
        self, *, limit: int = 250, active: bool | None = None
    ) -> list[dict[str, Any]]:
        """Returns all n8n workflows visible to the API key holder.

        Paginates server-side via `cursor`. Stops at `limit` rows total
        (defaults to a safe cap; an editor with 250+ workflows can
        bump it or add filters).
        """
        out: list[dict[str, Any]] = []
        cursor: str | None = None
        http = await self._ensure_http()

        while len(out) < limit:
            params: dict[str, Any] = {"limit": min(100, limit - len(out))}
            if cursor:
                params["cursor"] = cursor
            if active is not None:
                params["active"] = "true" if active else "false"

            response = await http.get(
                f"{self.base_url}/workflows",
                headers={"X-N8N-API-KEY": self.api_key},
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            body = response.json()
            page = body.get("data", [])
            out.extend(page)
            cursor = body.get("nextCursor")
            if not cursor or not page:
                break

        return out[:limit]

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(verify=self._verify_ssl)
            self._owns_http = True
        return self._http
