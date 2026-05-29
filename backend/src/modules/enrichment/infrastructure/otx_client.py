"""Cliente httpx para AlienVault OTX API v1."""
import logging
import time

import httpx
from pydantic import SecretStr
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.src.modules.enrichment.application.dtos import ProviderVerdict

logger = logging.getLogger(__name__)

_BASE_URL = "https://otx.alienvault.com/api/v1"


def _is_retriable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 502, 503, 504)
    return False


class OTXClient:
    def __init__(
        self,
        api_key: SecretStr,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"X-OTX-API-KEY": api_key.get_secret_value()},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retriable),
        reraise=True,
    )
    async def _get(self, path: str) -> dict:
        resp = await self._client.get(path)
        resp.raise_for_status()
        return resp.json()

    async def lookup_file(self, sha256: str) -> ProviderVerdict:
        t0 = time.monotonic()
        try:
            data = await self._get(f"/indicators/file/{sha256}/general")
            pulse_count = data.get("pulse_info", {}).get("count", 0)
            if pulse_count > 5:
                rep = "malicious"
            elif pulse_count > 0:
                rep = "suspicious"
            else:
                rep = "harmless"
            raw = {
                "pulse_count": pulse_count,
                "malware_families": data.get("malware_families", []),
            }
            logger.info(
                "otx.lookup_file indicator=%s duration_ms=%.0f status=%s",
                sha256, (time.monotonic() - t0) * 1000, rep,
            )
            return ProviderVerdict(
                provider="otx",
                indicator=sha256,
                indicator_type="hash",
                malicious_count=pulse_count,
                total_engines=None,
                reputation=rep,
                raw=raw,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ProviderVerdict(
                    provider="otx",
                    indicator=sha256,
                    indicator_type="hash",
                    reputation="unknown",
                    error="not found in OTX",
                )
            raise
        except Exception as e:
            logger.warning("otx.lookup_file failed indicator=%s error=%s", sha256, e)
            return ProviderVerdict(
                provider="otx",
                indicator=sha256,
                indicator_type="hash",
                reputation="unknown",
                error=str(e),
            )

    async def lookup_ip(self, ip: str) -> ProviderVerdict:
        t0 = time.monotonic()
        try:
            data = await self._get(f"/indicators/IPv4/{ip}/general")
            pulse_count = data.get("pulse_info", {}).get("count", 0)
            if pulse_count > 5:
                rep = "malicious"
            elif pulse_count > 0:
                rep = "suspicious"
            else:
                rep = "harmless"
            raw = {
                "pulse_count": pulse_count,
                "country_name": data.get("country_name"),
                "reputation": data.get("reputation", 0),
            }
            logger.info(
                "otx.lookup_ip indicator=%s duration_ms=%.0f status=%s",
                ip, (time.monotonic() - t0) * 1000, rep,
            )
            return ProviderVerdict(
                provider="otx",
                indicator=ip,
                indicator_type="ip",
                malicious_count=pulse_count,
                total_engines=None,
                reputation=rep,
                raw=raw,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ProviderVerdict(
                    provider="otx",
                    indicator=ip,
                    indicator_type="ip",
                    reputation="unknown",
                    error="not found in OTX",
                )
            raise
        except Exception as e:
            logger.warning("otx.lookup_ip failed indicator=%s error=%s", ip, e)
            return ProviderVerdict(
                provider="otx",
                indicator=ip,
                indicator_type="ip",
                reputation="unknown",
                error=str(e),
            )
