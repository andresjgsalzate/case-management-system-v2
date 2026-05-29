"""Use cases para el módulo de enrichment."""
import asyncio
from collections.abc import Coroutine
from typing import Any

from pydantic import SecretStr

from backend.src.modules.enrichment.application.dtos import (
    ProviderVerdict,
    ReputationRequest,
    ReputationResponse,
    is_valid_hash,
    is_valid_ip,
)
from backend.src.modules.enrichment.infrastructure.otx_client import OTXClient
from backend.src.modules.enrichment.infrastructure.virustotal_client import (
    VirusTotalClient,
)


def _summarize(verdicts: list[ProviderVerdict]) -> dict[str, int]:
    summary: dict[str, int] = {
        "malicious": 0, "suspicious": 0, "harmless": 0, "unknown": 0, "errors": 0,
    }
    for v in verdicts:
        if v.error:
            summary["errors"] += 1
        summary[v.reputation] = summary.get(v.reputation, 0) + 1
    return summary


async def _static(verdict: ProviderVerdict) -> ProviderVerdict:
    return verdict


class EnrichmentUseCases:
    def __init__(
        self,
        vt_api_key: SecretStr | None,
        otx_api_key: SecretStr | None,
    ) -> None:
        self._vt = VirusTotalClient(vt_api_key) if vt_api_key else None
        self._otx = OTXClient(otx_api_key) if otx_api_key else None

    async def get_reputation(self, req: ReputationRequest) -> ReputationResponse:
        coros: list[Coroutine[Any, Any, ProviderVerdict]] = []

        for h in req.hashes:
            if not is_valid_hash(h):
                coros.append(_static(ProviderVerdict(
                    provider="virustotal", indicator=h, indicator_type="hash",
                    reputation="unknown", error="invalid format",
                )))
                coros.append(_static(ProviderVerdict(
                    provider="otx", indicator=h, indicator_type="hash",
                    reputation="unknown", error="invalid format",
                )))
                continue
            coros.append(
                self._vt.lookup_file(h) if self._vt
                else _static(ProviderVerdict(
                    provider="virustotal", indicator=h, indicator_type="hash",
                    reputation="unknown", error="API key not configured",
                ))
            )
            coros.append(
                self._otx.lookup_file(h) if self._otx
                else _static(ProviderVerdict(
                    provider="otx", indicator=h, indicator_type="hash",
                    reputation="unknown", error="API key not configured",
                ))
            )

        for ip in req.ips:
            if not is_valid_ip(ip):
                coros.append(_static(ProviderVerdict(
                    provider="virustotal", indicator=ip, indicator_type="ip",
                    reputation="unknown", error="invalid format",
                )))
                coros.append(_static(ProviderVerdict(
                    provider="otx", indicator=ip, indicator_type="ip",
                    reputation="unknown", error="invalid format",
                )))
                continue
            coros.append(
                self._vt.lookup_ip(ip) if self._vt
                else _static(ProviderVerdict(
                    provider="virustotal", indicator=ip, indicator_type="ip",
                    reputation="unknown", error="API key not configured",
                ))
            )
            coros.append(
                self._otx.lookup_ip(ip) if self._otx
                else _static(ProviderVerdict(
                    provider="otx", indicator=ip, indicator_type="ip",
                    reputation="unknown", error="API key not configured",
                ))
            )

        if not coros:
            return ReputationResponse(verdicts=[], summary=_summarize([]))

        results = await asyncio.gather(*coros, return_exceptions=True)
        verdicts: list[ProviderVerdict] = []
        for r in results:
            if isinstance(r, ProviderVerdict):
                verdicts.append(r)
            elif isinstance(r, BaseException):
                verdicts.append(ProviderVerdict(
                    provider="unknown",
                    indicator="unknown",
                    indicator_type="unknown",
                    reputation="unknown",
                    error=str(r),
                ))

        return ReputationResponse(verdicts=verdicts, summary=_summarize(verdicts))
