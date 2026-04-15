"""
Tenant filtering helpers.

Catalog data (statuses, priorities, origins, etc.) can be:
  - tenant_id = NULL  → system-wide defaults, visible to all tenants
  - tenant_id = X     → custom data for tenant X only

Queries should always include both, preferring tenant-specific over global.
"""
from sqlalchemy import or_


def catalog_filter(model_class, tenant_id: str | None):
    """
    Returns an OR condition: rows belonging to `tenant_id` OR global rows (tenant_id IS NULL).
    Use this for catalog/config data that has system-wide defaults.
    """
    return or_(
        model_class.tenant_id == tenant_id,
        model_class.tenant_id.is_(None),
    )
