"""Cliente httpx para Wazuh Manager REST API."""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import SecretStr
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.src.modules.wazuh_query.application.dtos import SyscheckMatch

logger = logging.getLogger(__name__)

# JWT cache: base_url → (token, expires_at)
_token_cache: dict[str, tuple[str, datetime]] = {}
_TOKEN_SAFETY_MARGIN = timedelta(minutes=1)

_SYSCHECK_PAGE_SIZE = 500


def _is_retriable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 502, 503, 504)
    return False


class WazuhClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: SecretStr,
        verify_ssl: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            verify=verify_ssl,
        )

    async def _ensure_token(self) -> str:
        cached = _token_cache.get(self._base_url)
        if cached:
            token, exp = cached
            if datetime.now(timezone.utc) < exp - _TOKEN_SAFETY_MARGIN:
                return token

        resp = await self._client.post(
            f"{self._base_url}/security/user/authenticate",
            auth=(self._username, self._password.get_secret_value()),
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["data"]["token"]
        # Wazuh default TTL is 900s (15 min)
        exp = datetime.now(timezone.utc) + timedelta(seconds=900)
        _token_cache[self._base_url] = (token, exp)
        return token

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retriable),
        reraise=True,
    )
    async def list_active_agents(self, limit: int = 500) -> list[dict]:
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{self._base_url}/agents",
            params={"status": "active", "limit": limit, "select": "id,name"},
            headers=self._auth_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("affected_items", [])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retriable),
        reraise=True,
    )
    async def syscheck_by_hash(
        self, agent_id: str, sha256: str, limit: int = _SYSCHECK_PAGE_SIZE
    ) -> list[dict]:
        token = await self._ensure_token()
        resp = await self._client.get(
            f"{self._base_url}/syscheck/{agent_id}",
            params={"sha256": sha256, "limit": limit},
            headers=self._auth_headers(token),
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("affected_items", [])

    async def find_by_hash(
        self,
        sha256: str,
        agent_id: str | None = None,
        match_limit: int = 200,
    ) -> tuple[list[SyscheckMatch], int, bool]:
        """Return (matches, queried_agents, truncated)."""
        t0 = time.monotonic()

        if agent_id:
            agents_to_query = [agent_id]
            agent_names: dict[str, str] = {}
        else:
            raw_agents = await self.list_active_agents()
            agents_to_query = [a["id"] for a in raw_agents]
            agent_names = {a["id"]: a.get("name", a["id"]) for a in raw_agents}

        sem = asyncio.Semaphore(10)

        async def _query(aid: str) -> list[dict]:
            async with sem:
                rows = await self.syscheck_by_hash(aid, sha256)
                return rows

        results = await asyncio.gather(
            *[_query(aid) for aid in agents_to_query],
            return_exceptions=True,
        )

        matches: list[SyscheckMatch] = []
        truncated = False

        for aid, result in zip(agents_to_query, results):
            if isinstance(result, BaseException):
                logger.warning(
                    "wazuh.syscheck agent=%s hash=%s error=%s", aid, sha256, result
                )
                continue
            for row in result:
                if len(matches) >= match_limit:
                    truncated = True
                    break
                matches.append(SyscheckMatch(
                    agent_id=aid,
                    agent_name=agent_names.get(aid, aid),
                    file_path=row.get("file", ""),
                    file_size=row.get("size"),
                    sha256=row.get("sha256", sha256),
                    md5=row.get("md5"),
                    last_modified=_parse_ts(row.get("date")),
                ))

        logger.info(
            "wazuh.find_by_hash hash=%s queried=%d matches=%d duration_ms=%.0f",
            sha256, len(agents_to_query), len(matches),
            (time.monotonic() - t0) * 1000,
        )
        return matches, len(agents_to_query), truncated


def _parse_ts(value: str | int | None) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, int):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
