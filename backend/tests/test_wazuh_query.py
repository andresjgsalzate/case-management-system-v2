"""Tests para el módulo wazuh_query (cliente outbound a Wazuh Manager REST API).

Dos niveles:
- use_cases: validación de hash + wrapping en SyscheckResponse (cliente fake).
- WazuhClient: flujo auth (JWT) + parseo de /syscheck vía httpx.MockTransport.

NOTA: WazuhClient cachea el JWT en un global de módulo (_token_cache) por
base_url. El fixture autouse _clear_token_cache lo limpia entre tests para que
cada uno ejerza el POST de autenticación esperado.
"""
import httpx
import pytest
from pydantic import SecretStr

from backend.src.core.exceptions import BusinessRuleError
from backend.src.modules.wazuh_query.application.dtos import SyscheckMatch, SyscheckResponse
from backend.src.modules.wazuh_query.application.use_cases import WazuhQueryUseCases
from backend.src.modules.wazuh_query.infrastructure import wazuh_client as wc_module
from backend.src.modules.wazuh_query.infrastructure.wazuh_client import WazuhClient

_SHA256 = "a" * 64
_BASE = "https://wazuh.test:55000"


@pytest.fixture(autouse=True)
def _clear_token_cache():
    wc_module._token_cache.clear()
    yield
    wc_module._token_cache.clear()


# ─────────────────────────────────────────────────────────────
# use_cases (cliente fake)
# ─────────────────────────────────────────────────────────────
class _FakeWazuhClient:
    def __init__(self, result: tuple[list[SyscheckMatch], int, bool]):
        self._result = result
        self.called_with: dict | None = None

    async def find_by_hash(self, sha256: str, agent_id=None, match_limit: int = 200):
        self.called_with = {"sha256": sha256, "agent_id": agent_id, "match_limit": match_limit}
        return self._result


@pytest.mark.parametrize("bad", ["", "abc", "a" * 63, "a" * 65, "z" * 64])
async def test_find_by_hash_rejects_non_sha256(bad):
    uc = WazuhQueryUseCases(_FakeWazuhClient(([], 0, False)))  # type: ignore[arg-type]
    with pytest.raises(BusinessRuleError):
        await uc.find_by_hash(sha256=bad)


async def test_find_by_hash_wraps_client_result():
    matches = [
        SyscheckMatch(agent_id="001", agent_name="srv-01", file_path="/bin/x", sha256=_SHA256),
    ]
    fake = _FakeWazuhClient((matches, 3, True))
    uc = WazuhQueryUseCases(fake)  # type: ignore[arg-type]

    res = await uc.find_by_hash(sha256=_SHA256, agent_id="001")

    assert isinstance(res, SyscheckResponse)
    assert res.hash == _SHA256
    assert res.matches == matches
    assert res.queried_agents == 3
    assert res.truncated is True
    assert fake.called_with == {"sha256": _SHA256, "agent_id": "001", "match_limit": 200}


# ─────────────────────────────────────────────────────────────
# WazuhClient (httpx.MockTransport)
# ─────────────────────────────────────────────────────────────
def _wazuh_client(handler) -> WazuhClient:
    inner = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WazuhClient(
        base_url=_BASE, username="wazuh", password=SecretStr("pw"),
        verify_ssl=False, client=inner,
    )


def _auth_response() -> httpx.Response:
    return httpx.Response(200, json={"data": {"token": "jwt-token"}})


async def test_client_authenticates_then_queries_single_agent():
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path.endswith("/security/user/authenticate"):
            assert request.method == "POST"
            return _auth_response()
        if "/syscheck/007" in request.url.path:
            return httpx.Response(200, json={"data": {"affected_items": [
                {"file": "/usr/bin/evil", "size": 1024, "sha256": _SHA256,
                 "md5": "d" * 32, "date": "2026-01-15T10:00:00Z"},
            ]}})
        raise AssertionError(f"unexpected path {request.url.path}")

    matches, queried, truncated = await _wazuh_client(handler).find_by_hash(
        sha256=_SHA256, agent_id="007",
    )

    assert queried == 1
    assert truncated is False
    assert len(matches) == 1
    m = matches[0]
    assert m.agent_id == "007"
    assert m.agent_name == "007"  # sin lista de agentes, cae al id
    assert m.file_path == "/usr/bin/evil"
    assert m.last_modified is not None
    assert any(p.endswith("/security/user/authenticate") for p in seen_paths)


async def test_client_lists_agents_when_no_agent_id():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/security/user/authenticate"):
            return _auth_response()
        if path.endswith("/agents"):
            return httpx.Response(200, json={"data": {"affected_items": [
                {"id": "001", "name": "srv-01"},
                {"id": "002", "name": "srv-02"},
            ]}})
        if "/syscheck/001" in path:
            return httpx.Response(200, json={"data": {"affected_items": [
                {"file": "/a", "sha256": _SHA256},
            ]}})
        if "/syscheck/002" in path:
            return httpx.Response(200, json={"data": {"affected_items": []}})
        raise AssertionError(f"unexpected path {path}")

    matches, queried, truncated = await _wazuh_client(handler).find_by_hash(sha256=_SHA256)

    assert queried == 2
    assert len(matches) == 1
    assert matches[0].agent_id == "001"
    assert matches[0].agent_name == "srv-01"  # nombre desde la lista de agentes


async def test_client_truncates_at_match_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/security/user/authenticate"):
            return _auth_response()
        if "/syscheck/007" in path:
            rows = [{"file": f"/f{i}", "sha256": _SHA256} for i in range(5)]
            return httpx.Response(200, json={"data": {"affected_items": rows}})
        raise AssertionError(f"unexpected path {path}")

    matches, queried, truncated = await _wazuh_client(handler).find_by_hash(
        sha256=_SHA256, agent_id="007", match_limit=2,
    )

    assert len(matches) == 2
    assert truncated is True


async def test_client_skips_agent_on_error():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/security/user/authenticate"):
            return _auth_response()
        if path.endswith("/agents"):
            return httpx.Response(200, json={"data": {"affected_items": [
                {"id": "001", "name": "srv-01"},
                {"id": "002", "name": "srv-02"},
            ]}})
        if "/syscheck/001" in path:
            return httpx.Response(200, json={"data": {"affected_items": [
                {"file": "/a", "sha256": _SHA256},
            ]}})
        if "/syscheck/002" in path:
            return httpx.Response(500, json={"error": "boom"})
        raise AssertionError(f"unexpected path {path}")

    matches, queried, truncated = await _wazuh_client(handler).find_by_hash(sha256=_SHA256)

    # agente 002 falla → se omite; el match de 001 sigue presente.
    assert queried == 2
    assert len(matches) == 1
    assert matches[0].agent_id == "001"


async def test_client_syscheck_404_yields_no_matches():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/security/user/authenticate"):
            return _auth_response()
        if "/syscheck/007" in path:
            return httpx.Response(404, json={"error": "no syscheck data"})
        raise AssertionError(f"unexpected path {path}")

    matches, queried, truncated = await _wazuh_client(handler).find_by_hash(
        sha256=_SHA256, agent_id="007",
    )

    assert queried == 1
    assert matches == []
