"""Velociraptor health probe for the integration_health subsystem.

Registered into the operational_center health probe registry
(``HEALTH_PROBES``) at app startup, keyed by ``source_type='velociraptor'``.
The refresh job invokes us once per active source and stores the returned
dict in ``integration_health.extra_metrics``.

Never raises: a Velo outage must not break the refresh loop for OTHER
sources (Wazuh, n8n, etc). Errors are returned as ``{"error": "..."}``.
"""
import logging

from backend.src.modules.forensic.infrastructure.velo_client import (
    get_velo_client,
)

logger = logging.getLogger(__name__)


async def velociraptor_health_probe(source) -> dict:
    """Return a metrics dict for a Velociraptor ``IntegrationSource``.

    Shape on success: ``{online_clients, total_clients, active_hunts, version}``.
    Shape on failure: ``{"error": "<short message>"}``.
    """
    try:
        client = get_velo_client()
        return await client.health_check()
    except Exception as e:
        logger.error("Velociraptor health probe failed: %s", e)
        return {"error": str(e)[:200]}
