"""Tests para el módulo enrichment (VirusTotal + AlienVault OTX).

Dos niveles:
- use_cases: lógica de orquestación (validación, fallbacks sin key, summarize,
  manejo de excepciones de proveedor) — sin HTTP, con proveedores fake.
- clients: parsing de respuestas VT/OTX vía httpx.MockTransport — sin red.
"""
import httpx
import pytest
from pydantic import SecretStr

from backend.src.modules.enrichment.application.dtos import (
    ProviderVerdict,
    ReputationRequest,
    is_valid_hash,
    is_valid_ip,
)
from backend.src.modules.enrichment.application.use_cases import (
    EnrichmentUseCases,
    _summarize,
)
from backend.src.modules.enrichment.infrastructure.otx_client import OTXClient
from backend.src.modules.enrichment.infrastructure.virustotal_client import (
    VirusTotalClient,
)

_SHA256 = "a" * 64
_MD5 = "b" * 32
_SHA1 = "c" * 40


# ─────────────────────────────────────────────────────────────
# DTOs / validadores puros
# ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("value", [_MD5, _SHA1, _SHA256, "ABCDEF0123456789" * 4])
def test_is_valid_hash_accepts_md5_sha1_sha256(value):
    assert is_valid_hash(value) is True


@pytest.mark.parametrize("value", ["", "xyz", "g" * 64, "a" * 63, "a" * 65])
def test_is_valid_hash_rejects_garbage(value):
    assert is_valid_hash(value) is False


@pytest.mark.parametrize("value", ["1.2.3.4", "255.255.255.255", "::1", "2001:db8::1"])
def test_is_valid_ip_accepts_v4_and_v6(value):
    assert is_valid_ip(value) is True


@pytest.mark.parametrize("value", ["", "999.1.1.1", "not-an-ip", "1.2.3"])
def test_is_valid_ip_rejects_garbage(value):
    assert is_valid_ip(value) is False


def test_reputation_request_strips_and_dedupes():
    req = ReputationRequest(hashes=["  aaa  ", "aaa", "", "  ", "bbb"], ips=[" 1.2.3.4 "])
    assert req.hashes == ["aaa", "bbb"]
    assert req.ips == ["1.2.3.4"]


def test_reputation_request_forbids_extra_fields():
    with pytest.raises(Exception):
        ReputationRequest(hashes=[], ips=[], bogus="x")


# ─────────────────────────────────────────────────────────────
# _summarize
# ─────────────────────────────────────────────────────────────
def test_summarize_counts_by_reputation_and_errors():
    verdicts = [
        ProviderVerdict(provider="vt", indicator="x", indicator_type="hash", reputation="malicious"),
        ProviderVerdict(provider="vt", indicator="y", indicator_type="hash", reputation="harmless"),
        ProviderVerdict(provider="otx", indicator="z", indicator_type="ip", reputation="unknown", error="boom"),
    ]
    summary = _summarize(verdicts)
    assert summary["malicious"] == 1
    assert summary["harmless"] == 1
    # El verdict con error suma a errors Y a unknown (reputation="unknown").
    assert summary["errors"] == 1
    assert summary["unknown"] == 1


# ─────────────────────────────────────────────────────────────
# Proveedor fake para use_cases (sin HTTP)
# ─────────────────────────────────────────────────────────────
class _FakeProvider:
    def __init__(self, *, verdict: ProviderVerdict | None = None, exc: Exception | None = None):
        self._verdict = verdict
        self._exc = exc
        self.calls: list[str] = []

    async def lookup_file(self, indicator: str) -> ProviderVerdict:
        self.calls.append(indicator)
        if self._exc:
            raise self._exc
        return self._verdict

    async def lookup_ip(self, indicator: str) -> ProviderVerdict:
        self.calls.append(indicator)
        if self._exc:
            raise self._exc
        return self._verdict


def _uc_with_fakes(vt: _FakeProvider | None, otx: _FakeProvider | None) -> EnrichmentUseCases:
    uc = EnrichmentUseCases(vt_api_key=SecretStr("vt"), otx_api_key=SecretStr("otx"))
    uc._vt = vt  # type: ignore[assignment]
    uc._otx = otx  # type: ignore[assignment]
    return uc


# ─────────────────────────────────────────────────────────────
# get_reputation
# ─────────────────────────────────────────────────────────────
async def test_get_reputation_empty_request_returns_empty():
    uc = EnrichmentUseCases(vt_api_key=None, otx_api_key=None)
    res = await uc.get_reputation(ReputationRequest(hashes=[], ips=[]))
    assert res.verdicts == []
    assert res.summary["malicious"] == 0
    assert res.summary["errors"] == 0


async def test_get_reputation_invalid_hash_yields_two_invalid_verdicts():
    uc = EnrichmentUseCases(vt_api_key=None, otx_api_key=None)
    res = await uc.get_reputation(ReputationRequest(hashes=["not-a-hash"], ips=[]))
    assert len(res.verdicts) == 2  # vt + otx
    assert {v.provider for v in res.verdicts} == {"virustotal", "otx"}
    assert all(v.error == "invalid format" for v in res.verdicts)
    assert all(v.reputation == "unknown" for v in res.verdicts)


async def test_get_reputation_valid_hash_no_key_reports_not_configured():
    uc = EnrichmentUseCases(vt_api_key=None, otx_api_key=None)
    res = await uc.get_reputation(ReputationRequest(hashes=[_SHA256], ips=[]))
    assert len(res.verdicts) == 2
    assert all(v.error == "API key not configured" for v in res.verdicts)


async def test_get_reputation_valid_hash_with_providers_aggregates():
    vt_verdict = ProviderVerdict(
        provider="virustotal", indicator=_SHA256, indicator_type="hash",
        malicious_count=15, total_engines=70, reputation="malicious",
    )
    otx_verdict = ProviderVerdict(
        provider="otx", indicator=_SHA256, indicator_type="hash",
        malicious_count=7, reputation="malicious",
    )
    vt, otx = _FakeProvider(verdict=vt_verdict), _FakeProvider(verdict=otx_verdict)
    uc = _uc_with_fakes(vt, otx)

    res = await uc.get_reputation(ReputationRequest(hashes=[_SHA256], ips=[]))

    assert len(res.verdicts) == 2
    assert res.summary["malicious"] == 2
    assert vt.calls == [_SHA256]
    assert otx.calls == [_SHA256]


async def test_get_reputation_valid_ip_uses_lookup_ip():
    verdict = ProviderVerdict(
        provider="virustotal", indicator="1.2.3.4", indicator_type="ip",
        reputation="harmless",
    )
    vt, otx = _FakeProvider(verdict=verdict), _FakeProvider(verdict=verdict)
    uc = _uc_with_fakes(vt, otx)

    res = await uc.get_reputation(ReputationRequest(hashes=[], ips=["1.2.3.4"]))

    assert len(res.verdicts) == 2
    assert vt.calls == ["1.2.3.4"]  # lookup_ip recibió la IP


async def test_get_reputation_provider_exception_becomes_error_verdict():
    vt = _FakeProvider(exc=RuntimeError("provider down"))
    otx_verdict = ProviderVerdict(
        provider="otx", indicator=_SHA256, indicator_type="hash", reputation="harmless",
    )
    otx = _FakeProvider(verdict=otx_verdict)
    uc = _uc_with_fakes(vt, otx)

    res = await uc.get_reputation(ReputationRequest(hashes=[_SHA256], ips=[]))

    errored = [v for v in res.verdicts if v.error]
    assert len(errored) == 1
    assert "provider down" in errored[0].error
    assert res.summary["errors"] == 1


# ─────────────────────────────────────────────────────────────
# VirusTotalClient (httpx.MockTransport)
# ─────────────────────────────────────────────────────────────
def _vt_client(handler) -> VirusTotalClient:
    inner = httpx.AsyncClient(
        base_url="https://www.virustotal.com/api/v3",
        transport=httpx.MockTransport(handler),
    )
    return VirusTotalClient(SecretStr("k"), client=inner)


async def test_vt_lookup_file_parses_malicious():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/files/{_SHA256}")
        return httpx.Response(200, json={"data": {"attributes": {
            "last_analysis_stats": {"malicious": 15, "suspicious": 2, "harmless": 50, "undetected": 3},
            "last_analysis_date": 1700000000,
            "tags": ["trojan"], "meaningful_name": "evil.exe",
        }}})

    verdict = await _vt_client(handler).lookup_file(_SHA256)
    assert verdict.reputation == "malicious"
    assert verdict.malicious_count == 15
    assert verdict.total_engines == 70
    assert verdict.last_analysis_date is not None


async def test_vt_lookup_file_harmless_when_no_detections():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"attributes": {
            "last_analysis_stats": {"malicious": 0, "suspicious": 0, "harmless": 60},
        }}})

    verdict = await _vt_client(handler).lookup_file(_SHA256)
    assert verdict.reputation == "harmless"


async def test_vt_lookup_file_suspicious_on_single_detection():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"attributes": {
            "last_analysis_stats": {"malicious": 1, "suspicious": 0, "harmless": 60},
        }}})

    verdict = await _vt_client(handler).lookup_file(_SHA256)
    assert verdict.reputation == "suspicious"


async def test_vt_lookup_file_404_returns_unknown():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": "NotFoundError"}})

    verdict = await _vt_client(handler).lookup_file(_SHA256)
    assert verdict.reputation == "unknown"
    assert verdict.error == "not found in VirusTotal"


async def test_vt_lookup_file_500_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {}})

    with pytest.raises(httpx.HTTPStatusError):
        await _vt_client(handler).lookup_file(_SHA256)


async def test_vt_lookup_ip_parses_country_and_reputation():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/ip_addresses/" in request.url.path
        return httpx.Response(200, json={"data": {"attributes": {
            "last_analysis_stats": {"malicious": 5, "harmless": 40},
            "country": "RU", "asn": 1234,
        }}})

    verdict = await _vt_client(handler).lookup_ip("1.2.3.4")
    assert verdict.indicator_type == "ip"
    assert verdict.reputation == "malicious"
    assert verdict.raw["country"] == "RU"


# ─────────────────────────────────────────────────────────────
# OTXClient (httpx.MockTransport)
# ─────────────────────────────────────────────────────────────
def _otx_client(handler) -> OTXClient:
    inner = httpx.AsyncClient(
        base_url="https://otx.alienvault.com/api/v1",
        transport=httpx.MockTransport(handler),
    )
    return OTXClient(SecretStr("k"), client=inner)


async def test_otx_lookup_file_malicious_on_many_pulses():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/indicators/file/" in request.url.path
        return httpx.Response(200, json={
            "pulse_info": {"count": 7}, "malware_families": ["Emotet"],
        })

    verdict = await _otx_client(handler).lookup_file(_SHA256)
    assert verdict.reputation == "malicious"
    assert verdict.malicious_count == 7


async def test_otx_lookup_file_harmless_on_zero_pulses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pulse_info": {"count": 0}})

    verdict = await _otx_client(handler).lookup_file(_SHA256)
    assert verdict.reputation == "harmless"


async def test_otx_lookup_ip_404_returns_unknown():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    verdict = await _otx_client(handler).lookup_ip("8.8.8.8")
    assert verdict.reputation == "unknown"
    assert verdict.error == "not found in OTX"
