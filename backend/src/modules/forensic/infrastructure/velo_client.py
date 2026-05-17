"""Thin wrapper around pyvelociraptor.

All public methods accept ``org_id`` for per-tenant scoping via Velociraptor
native orgs. The wrapper exposes high-level operations (list_artifacts,
list_clients, create_hunt, get_hunt, cancel_hunt, stream_hunt_results,
health_check) but each one is implemented as a VQL query — VQL is the
canonical, version-stable Velociraptor interface.

Connection model follows ``pyvelociraptor.client_example.run``: load
api.config.yaml, build mTLS gRPC credentials, open a secure channel to
``config["api_connection_string"]``. The channel is lazy-created and
cached on the instance.
"""
import json
import logging
from typing import Any, AsyncIterator

import grpc
import pyvelociraptor
from pyvelociraptor import api_pb2, api_pb2_grpc

logger = logging.getLogger(__name__)


class VelociraptorClient:
    def __init__(self, *, endpoint: str, api_config_path: str):
        # ``endpoint`` is retained for diagnostics/logging only — the actual
        # connection string is taken from the api.config.yaml so the cert
        # SAN matches the address used.
        self.endpoint = endpoint
        self.api_config_path = api_config_path
        self._config: dict | None = None
        self._channel: grpc.Channel | None = None
        self._stub: api_pb2_grpc.APIStub | None = None

    def _load_config(self) -> dict:
        if self._config is None:
            cfg = pyvelociraptor.LoadConfigFile(self.api_config_path)
            if not isinstance(cfg, dict):
                raise RuntimeError(
                    f"Velociraptor config at {self.api_config_path} "
                    f"did not load as a dict (got {type(cfg).__name__})"
                )
            self._config = cfg
        return self._config

    def _get_stub(self) -> api_pb2_grpc.APIStub:
        if self._stub is None:
            cfg = self._load_config()
            creds = grpc.ssl_channel_credentials(
                root_certificates=cfg["ca_certificate"].encode("utf8"),
                private_key=cfg["client_private_key"].encode("utf8"),
                certificate_chain=cfg["client_cert"].encode("utf8"),
            )
            options = (("grpc.ssl_target_name_override", "VelociraptorServer"),)
            self._channel = grpc.secure_channel(
                cfg["api_connection_string"], creds, options
            )
            self._stub = api_pb2_grpc.APIStub(self._channel)
        return self._stub

    async def _query_vql(
        self,
        *,
        org_id: str,
        query: str,
        env: dict[str, Any] | None = None,
        timeout: int = 0,
    ) -> list[dict]:
        """Run a VQL query against Velociraptor and return rows.

        ``org_id`` scopes the query to a specific Velociraptor org. The
        underlying gRPC iterator is synchronous; callers that need true
        non-blocking behaviour should run this in an executor.
        """
        stub = self._get_stub()
        env_pairs = [
            dict(key=k, value=str(v)) for k, v in (env or {}).items()
        ]
        request = api_pb2.VQLCollectorArgs(
            org_id=org_id,
            max_wait=1,
            max_row=10000,
            timeout=timeout,
            Query=[api_pb2.VQLRequest(Name="cms_query", VQL=query)],
            env=env_pairs,
        )

        rows: list[dict] = []
        try:
            for response in stub.Query(request):
                if response.Response:
                    parsed = json.loads(response.Response)
                    if isinstance(parsed, list):
                        rows.extend(parsed)
                    else:
                        rows.append(parsed)
        except grpc.RpcError as e:
            logger.error(
                "Velociraptor VQL error on org=%s: %s", org_id, e
            )
            raise
        return rows

    async def list_artifacts(
        self, *, org_id: str, search_term: str = ""
    ) -> list[dict]:
        """Return all available artifacts in the org."""
        query = (
            "SELECT name, type, description, parameters "
            "FROM artifact_definitions()"
        )
        if search_term:
            query += f" WHERE name =~ {search_term!r}"
        return await self._query_vql(org_id=org_id, query=query)

    async def list_clients(
        self,
        *,
        org_id: str,
        label: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Return clients in the org. Each: {client_id, hostname, os, last_seen_at}."""
        select_cols = (
            "SELECT client_id, os_info.hostname AS hostname, "
            "os_info.system AS os, last_seen_at "
        )
        if label:
            query = (
                f"{select_cols}FROM clients(search='label:{label}') "
                f"LIMIT {limit}"
            )
        else:
            query = f"{select_cols}FROM clients() LIMIT {limit}"
        return await self._query_vql(org_id=org_id, query=query)

    async def get_client(
        self, *, org_id: str, client_id: str
    ) -> dict | None:
        rows = await self._query_vql(
            org_id=org_id,
            query=(
                "SELECT client_id, os_info.hostname AS hostname, "
                "os_info.system AS os, last_seen_at "
                f"FROM clients(client_id={client_id!r})"
            ),
        )
        return rows[0] if rows else None

    async def create_hunt(
        self,
        *,
        org_id: str,
        artifact_name: str,
        parameters: dict,
        client_ids: list[str] | None = None,
        labels: list[str] | None = None,
        description: str = "",
    ) -> str:
        """Create a hunt and return its hunt_id (``H.XXXXXX``).

        Either ``client_ids`` or ``labels`` must be supplied.
        """
        if not client_ids and not labels:
            raise ValueError("Must specify client_ids or labels")

        query = (
            "LET hunt <= hunt(description=DESCRIPTION, "
            "artifacts=ARTIFACTS, parameters=PARAMS, expires=EXPIRES) "
            "SELECT hunt.hunt_id AS hunt_id FROM scope()"
        )
        env = {
            "DESCRIPTION": description,
            "ARTIFACTS": [artifact_name],
            "PARAMS": parameters,
            "EXPIRES": "now() + 86400",
        }
        if client_ids:
            env["CLIENT_IDS"] = client_ids
        if labels:
            env["LABELS"] = labels

        rows = await self._query_vql(org_id=org_id, query=query, env=env)
        if not rows:
            raise RuntimeError(
                "Velociraptor returned no hunt_id from CreateHunt VQL"
            )
        return rows[0]["hunt_id"]

    async def get_hunt(self, *, org_id: str, hunt_id: str) -> dict:
        rows = await self._query_vql(
            org_id=org_id,
            query=f"SELECT * FROM hunts(hunt_id={hunt_id!r})",
        )
        if not rows:
            raise RuntimeError(f"Hunt {hunt_id} not found")
        return rows[0]

    async def cancel_hunt(self, *, org_id: str, hunt_id: str) -> None:
        await self._query_vql(
            org_id=org_id,
            query=f"SELECT hunt_id FROM cancel_hunt(hunt_id={hunt_id!r})",
        )

    async def stream_hunt_results(
        self, *, org_id: str, hunt_id: str, source: str
    ) -> AsyncIterator[dict]:
        rows = await self._query_vql(
            org_id=org_id,
            query=(
                f"SELECT * FROM hunt_results("
                f"hunt_id={hunt_id!r}, artifact={source!r}, source={source!r})"
            ),
        )
        for row in rows:
            yield row

    async def health_check(self) -> dict:
        """Return ``{online_clients, total_clients, active_hunts, version, error?}``.

        Aggregates three VQL queries against the admin (``root``) org so the
        result reflects the whole deployment, not a single tenant.
        """
        org_id = "root"
        try:
            clients = await self._query_vql(
                org_id=org_id,
                query=(
                    "SELECT count(items=client_id) AS total, "
                    "count(items=client_id, filter=last_seen_at > "
                    "now() - 300) AS online FROM clients()"
                ),
            )
            hunts = await self._query_vql(
                org_id=org_id,
                query=(
                    "SELECT count() AS active_hunts FROM hunts() "
                    "WHERE state = 'RUNNING'"
                ),
            )
            version = await self._query_vql(
                org_id=org_id,
                query="SELECT version FROM info()",
            )
            return {
                "online_clients": (clients[0].get("online") if clients else 0) or 0,
                "total_clients": (clients[0].get("total") if clients else 0) or 0,
                "active_hunts": (hunts[0].get("active_hunts") if hunts else 0) or 0,
                "version": (
                    version[0].get("version", {}).get("version")
                    if version else None
                ),
            }
        except Exception as e:
            logger.error("Velociraptor health_check failed: %s", e)
            return {"error": str(e)[:200]}


_client_singleton: VelociraptorClient | None = None


def get_velo_client() -> VelociraptorClient:
    """Return the process-wide ``VelociraptorClient``. Raises if not configured."""
    global _client_singleton
    if _client_singleton is None:
        from backend.src.core.config import get_settings
        s = get_settings()
        endpoint = getattr(s, "VELOCIRAPTOR_ENDPOINT", None)
        config_path = getattr(s, "VELOCIRAPTOR_API_CONFIG_PATH", None)
        if not endpoint or not config_path:
            raise RuntimeError(
                "VELOCIRAPTOR_ENDPOINT and VELOCIRAPTOR_API_CONFIG_PATH "
                "must be set in settings."
            )
        _client_singleton = VelociraptorClient(
            endpoint=endpoint,
            api_config_path=config_path,
        )
    return _client_singleton
