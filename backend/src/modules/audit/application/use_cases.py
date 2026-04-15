from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.audit.infrastructure.models import AuditLogModel


class AuditUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_logs(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogModel]:
        stmt = select(AuditLogModel).order_by(AuditLogModel.created_at.desc())
        if entity_type:
            stmt = stmt.where(AuditLogModel.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLogModel.entity_id == entity_id)
        if actor_id:
            stmt = stmt.where(AuditLogModel.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditLogModel.action == action)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resolve_labels(
        self, logs: list[AuditLogModel]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """
        Returns:
          actor_names  : {actor_id -> full_name}
          entity_labels: {entity_id -> human-readable label}
        Uses batch queries — one per table — instead of N individual lookups.
        """
        from backend.src.modules.users.infrastructure.models import UserModel
        from backend.src.modules.cases.infrastructure.models import CaseModel

        # ── Actor names (single batch query) ─────────────────────────────────
        actor_ids = {log.actor_id for log in logs if log.actor_id}
        actor_names: dict[str, str] = {}
        if actor_ids:
            rows = await self.db.execute(
                select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(actor_ids))
            )
            actor_names = {row.id: row.full_name for row in rows.all()}

        # ── Entity labels grouped by table name ───────────────────────────────
        entity_labels: dict[str, str] = {}
        by_type: dict[str, set[str]] = {}
        for log in logs:
            by_type.setdefault(log.entity_type, set()).add(log.entity_id)

        # cases → "REQ-001 — Título del caso"
        if "cases" in by_type:
            rows = await self.db.execute(
                select(CaseModel.id, CaseModel.case_number, CaseModel.title)
                .where(CaseModel.id.in_(by_type["cases"]))
            )
            for row in rows.all():
                entity_labels[row.id] = f"{row.case_number} — {row.title}"

        # users → "Nombre completo (email)"
        if "users" in by_type:
            rows = await self.db.execute(
                select(UserModel.id, UserModel.full_name, UserModel.email)
                .where(UserModel.id.in_(by_type["users"]))
            )
            for row in rows.all():
                entity_labels[row.id] = f"{row.full_name} ({row.email})"

        # dispositions → item_name or title
        if "dispositions" in by_type:
            try:
                from backend.src.modules.dispositions.infrastructure.models import DispositionModel
                rows = await self.db.execute(
                    select(DispositionModel.id, DispositionModel.item_name, DispositionModel.title)
                    .where(DispositionModel.id.in_(by_type["dispositions"]))
                )
                for row in rows.all():
                    label = row.item_name or row.title or row.id
                    entity_labels[row.id] = label
            except Exception:
                pass

        # disposition_categories → name
        if "disposition_categories" in by_type:
            try:
                from backend.src.modules.dispositions.infrastructure.models import DispositionCategoryModel
                rows = await self.db.execute(
                    select(DispositionCategoryModel.id, DispositionCategoryModel.name)
                    .where(DispositionCategoryModel.id.in_(by_type["disposition_categories"]))
                )
                for row in rows.all():
                    entity_labels[row.id] = row.name
            except Exception:
                pass

        # roles → name
        if "roles" in by_type:
            try:
                rows = await self.db.execute(
                    text("SELECT id, name FROM roles WHERE id = ANY(:ids)"),
                    {"ids": list(by_type["roles"])},
                )
                for row in rows.all():
                    entity_labels[row.id] = row.name
            except Exception:
                pass

        # teams → name
        if "teams" in by_type:
            try:
                rows = await self.db.execute(
                    text("SELECT id, name FROM teams WHERE id = ANY(:ids)"),
                    {"ids": list(by_type["teams"])},
                )
                for row in rows.all():
                    entity_labels[row.id] = row.name
            except Exception:
                pass

        # kb_articles → title
        if "kb_articles" in by_type:
            try:
                rows = await self.db.execute(
                    text("SELECT id, title FROM kb_articles WHERE id = ANY(:ids)"),
                    {"ids": list(by_type["kb_articles"])},
                )
                for row in rows.all():
                    entity_labels[row.id] = row.title
            except Exception:
                pass

        # automation_rules → name
        if "automation_rules" in by_type:
            try:
                rows = await self.db.execute(
                    text("SELECT id, name FROM automation_rules WHERE id = ANY(:ids)"),
                    {"ids": list(by_type["automation_rules"])},
                )
                for row in rows.all():
                    entity_labels[row.id] = row.name
            except Exception:
                pass

        return actor_names, entity_labels

    async def resolve_fk_values(self, logs: list[AuditLogModel]) -> dict[str, str]:
        """
        Scans all changes dicts for known FK fields and batch-resolves their
        UUID values to human-readable labels.
        Returns a flat {uuid -> label} dict used to enrich changes before serialization.
        """
        # Map: field_name -> (table, label_column)
        FK_FIELD_TABLE: dict[str, tuple[str, str]] = {
            "status_id":      ("case_statuses",          "name"),
            "priority_id":    ("case_priorities",        "name"),
            "assigned_to":    ("users",                  "full_name"),
            "team_id":        ("teams",                  "name"),
            "role_id":        ("roles",                  "name"),
            "category_id":    ("disposition_categories", "name"),
            "application_id": ("applications",           "name"),
            "origin_id":      ("origins",                "name"),
            "created_by_id":  ("users",                  "full_name"),
            "approved_by_id": ("users",                  "full_name"),
            "created_by":     ("users",                  "full_name"),
        }

        # Collect unique UUIDs per table across all logs
        by_table: dict[str, set[str]] = {}
        for log in logs:
            if log.changes:
                for field, info in log.changes.items():
                    if field == "_snapshot" and isinstance(info, dict):
                        # INSERT/DELETE snapshot
                        for snap_field, snap_val in info.items():
                            if snap_field in FK_FIELD_TABLE and isinstance(snap_val, str) and len(snap_val) == 36:
                                table, _ = FK_FIELD_TABLE[snap_field]
                                by_table.setdefault(table, set()).add(snap_val)
                    elif field in FK_FIELD_TABLE and isinstance(info, dict):
                        table, _ = FK_FIELD_TABLE[field]
                        for val in [info.get("old"), info.get("new")]:
                            if val and isinstance(val, str) and len(val) == 36:
                                by_table.setdefault(table, set()).add(val)

            # Also resolve FK values in before_snapshot (UPDATE records)
            if log.before_snapshot:
                for snap_field, snap_val in log.before_snapshot.items():
                    if snap_field in FK_FIELD_TABLE and isinstance(snap_val, str) and len(snap_val) == 36:
                        table, _ = FK_FIELD_TABLE[snap_field]
                        by_table.setdefault(table, set()).add(snap_val)

        resolved: dict[str, str] = {}
        if not by_table:
            return resolved

        from backend.src.modules.users.infrastructure.models import UserModel

        for table, ids in by_table.items():
            id_list = list(ids)
            try:
                if table == "users":
                    rows = await self.db.execute(
                        select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(id_list))
                    )
                    for row in rows.all():
                        resolved[row.id] = row.full_name
                elif table == "disposition_categories":
                    from backend.src.modules.dispositions.infrastructure.models import DispositionCategoryModel
                    rows = await self.db.execute(
                        select(DispositionCategoryModel.id, DispositionCategoryModel.name)
                        .where(DispositionCategoryModel.id.in_(id_list))
                    )
                    for row in rows.all():
                        resolved[row.id] = row.name
                else:
                    rows = await self.db.execute(
                        text(f"SELECT id, name FROM {table} WHERE id = ANY(:ids)"),
                        {"ids": id_list},
                    )
                    for row in rows.all():
                        resolved[row.id] = row.name
            except Exception:
                pass

        return resolved

    async def list_timeline(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[AuditLogModel]:
        """
        Returns all audit events for a specific entity in chronological order (ASC).
        Used to reconstruct the complete history of a record from creation to present.
        """
        stmt = (
            select(AuditLogModel)
            .where(
                AuditLogModel.entity_type == entity_type,
                AuditLogModel.entity_id == entity_id,
            )
            .order_by(AuditLogModel.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_correlation(
        self,
        correlation_id: str,
    ) -> list[AuditLogModel]:
        """
        Returns all audit events that share the same correlation_id (same HTTP request).
        Used to answer: "what else changed in this same operation?"
        """
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.correlation_id == correlation_id)
            .order_by(AuditLogModel.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
