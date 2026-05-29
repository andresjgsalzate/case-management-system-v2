"""Cliente httpx para VirusTotal API v3."""
import logging
from datetime import datetime, timezone

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

_BASE_URL = "https://www.virustotal.com/api/v3"


def _is_retriable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 502, 503, 504)
    return False


class VirusTotalClient:
    def __init__(
        self,
        api_key: SecretStr,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"x-apikey": api_key.get_secret_value()},
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
        import time
        t0 = time.monotonic()
        try:
            data = await self._get(f"/files/{sha256}")
            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values()) if stats else None
            if malicious > 2:
                rep = "malicious"
            elif malicious > 0 or suspicious > 0:
                rep = "suspicious"
            else:
                rep = "harmless"
            last_date: datetime | None = None
            if ts := attrs.get("last_analysis_date"):
                last_date = datetime.fromtimestamp(ts, tz=timezone.utc)
            raw = {
                "last_analysis_stats": stats,
                "tags": attrs.get("tags", []),
                "meaningful_name": attrs.get("meaningful_name"),
                "type_description": attrs.get("type_description"),
            }
            logger.info(
                "vt.lookup_file indicator=%s duration_ms=%.0f status=%s",
                sha256, (time.monotonic() - t0) * 1000, rep,
            )
            return ProviderVerdict(
                provider="virustotal",
                indicator=sha256,
                indicator_type="hash",
                malicious_count=malicious,
                total_engines=total,
                reputation=rep,
                last_analysis_date=last_date,
                raw=raw,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ProviderVerdict(
                    provider="virustotal",
                    indicator=sha256,
                    indicator_type="hash",
                    reputation="unknown",
                    error="not found in VirusTotal",
                )
            raise
        except Exception as e:
            logger.warning("vt.lookup_file failed indicator=%s error=%s", sha256, e)
            return ProviderVerdict(
                provider="virustotal",
                indicator=sha256,
                indicator_type="hash",
                reputation="unknown",
                error=str(e),
            )

    async def lookup_ip(self, ip: str) -> ProviderVerdict:
        import time
        t0 = time.monotonic()
        try:
            data = await self._get(f"/ip_addresses/{ip}")
            attrs = data.get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            total = sum(stats.values()) if stats else None
            if malicious > 2:
                rep = "malicious"
            elif malicious > 0 or suspicious > 0:
                rep = "suspicious"
            else:
                rep = "harmless"
            last_date: datetime | None = None
            if ts := attrs.get("last_analysis_date"):
                last_date = datetime.fromtimestamp(ts, tz=timezone.utc)
            raw = {
                "last_analysis_stats": stats,
                "country": attrs.get("country"),
                "asn": attrs.get("asn"),
                "as_owner": attrs.get("as_owner"),
                "network": attrs.get("network"),
            }
            logger.info(
                "vt.lookup_ip indicator=%s duration_ms=%.0f status=%s",
                ip, (time.monotonic() - t0) * 1000, rep,
            )
            return ProviderVerdict(
                provider="virustotal",
                indicator=ip,
                indicator_type="ip",
                malicious_count=malicious,
                total_engines=total,
                reputation=rep,
                last_analysis_date=last_date,
                raw=raw,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ProviderVerdict(
                    provider="virustotal",
                    indicator=ip,
                    indicator_type="ip",
                    reputation="unknown",
                    error="not found in VirusTotal",
                )
            raise
        except Exception as e:
            logger.warning("vt.lookup_ip failed indicator=%s error=%s", ip, e)
            return ProviderVerdict(
                provider="virustotal",
                indicator=ip,
                indicator_type="ip",
                reputation="unknown",
                error=str(e),
            )
