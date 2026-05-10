from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MetricsUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_cases_by_status(self) -> list[dict[str, Any]]:
        result = await self.db.execute(text("""
            SELECT cs.name AS status_name, COUNT(c.id) AS count
            FROM cases c
            JOIN case_statuses cs ON cs.id = c.status_id
            WHERE c.is_archived = false
            GROUP BY cs.name
            ORDER BY count DESC
        """))
        rows = result.fetchall()
        return [{"status": r[0], "count": r[1]} for r in rows]

    async def get_cases_by_priority(self) -> list[dict[str, Any]]:
        result = await self.db.execute(text("""
            SELECT cp.name AS priority_name, cp.color, COUNT(c.id) AS count
            FROM cases c
            JOIN case_priorities cp ON cp.id = c.priority_id
            WHERE c.is_archived = false
            GROUP BY cp.name, cp.color
            ORDER BY count DESC
        """))
        rows = result.fetchall()
        return [{"priority_name": r[0], "color": r[1], "count": r[2]} for r in rows]

    async def get_cases_by_agent(self, limit: int = 10) -> list[dict[str, Any]]:
        result = await self.db.execute(
            text("""
                SELECT u.full_name, u.email, COUNT(c.id) AS assigned_cases
                FROM cases c
                JOIN users u ON u.id = c.assigned_to
                WHERE c.is_archived = false AND c.assigned_to IS NOT NULL
                GROUP BY u.id, u.full_name, u.email
                ORDER BY assigned_cases DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [{"full_name": r[0], "email": r[1], "assigned_cases": r[2]} for r in rows]

    async def get_cases_by_application(self) -> list[dict[str, Any]]:
        result = await self.db.execute(text("""
            SELECT a.name AS application, COUNT(c.id) AS count
            FROM cases c
            LEFT JOIN applications a ON a.id = c.application_id
            WHERE c.is_archived = false
            GROUP BY a.name
            ORDER BY count DESC
        """))
        rows = result.fetchall()
        return [{"application": r[0] or "Sin aplicación", "count": r[1]} for r in rows]

    async def get_cases_by_service_category(self) -> list[dict[str, Any]]:
        """Distribución de casos activos por categoría del catálogo de servicios.
        Casos sin catálogo (legacy) caen en bucket "Sin catálogo"."""
        result = await self.db.execute(text("""
            SELECT
                COALESCE(scc.name, 'Sin catálogo') AS category,
                scc.color AS color,
                COUNT(c.id) AS count
            FROM cases c
            LEFT JOIN service_catalog_items sci ON sci.id = c.service_item_id
            LEFT JOIN service_catalog_categories scc ON scc.id = sci.category_id
            WHERE c.is_archived = false
            GROUP BY scc.name, scc.color
            ORDER BY count DESC
        """))
        rows = result.fetchall()
        return [{"category": r[0], "color": r[1], "count": r[2]} for r in rows]

    async def get_top_service_items(self, limit: int = 10) -> list[dict[str, Any]]:
        """Top N tipos de solicitud por volumen de casos. Inner join — solo
        cuenta casos con catálogo asignado."""
        result = await self.db.execute(
            text("""
                SELECT
                    sci.name AS item_name,
                    scc.name AS category_name,
                    COUNT(c.id) AS count
                FROM cases c
                JOIN service_catalog_items sci ON sci.id = c.service_item_id
                JOIN service_catalog_categories scc ON scc.id = sci.category_id
                WHERE c.is_archived = false
                GROUP BY sci.id, sci.name, scc.name
                ORDER BY count DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [
            {"item_name": r[0], "category_name": r[1], "count": r[2]}
            for r in rows
        ]

    async def get_sla_compliance_rate(self) -> dict[str, Any]:
        # Solo contamos SLAs de casos activos y en estados no finales.
        # Casos archivados o cerrados ya no deben afectar la tasa de cumplimiento.
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE sr.is_breached = true) AS breached,
                COUNT(*) FILTER (WHERE sr.is_breached = false) AS met
            FROM sla_records sr
            JOIN cases c ON c.id = sr.case_id
            JOIN case_statuses cs ON cs.id = c.status_id
            WHERE c.is_archived = false
              AND cs.is_final = false
        """))
        row = result.fetchone()
        total = row[0] or 0
        breached = row[1] or 0
        met = row[2] or 0
        pct = round((met / total * 100), 2) if total > 0 else 100.0
        return {"total": total, "breached": breached, "met": met, "compliance_pct": pct}

    async def get_avg_resolution_minutes(self) -> dict[str, Any]:
        """Tiempo promedio de resolución en minutos (desde creación hasta cierre)."""
        result = await self.db.execute(text("""
            SELECT
                AVG(EXTRACT(EPOCH FROM (closed_at - created_at)) / 60)::int AS avg_minutes
            FROM cases
            WHERE closed_at IS NOT NULL
              AND is_archived = false
        """))
        row = result.fetchone()
        avg = row[0] or 0
        return {"avg_minutes": avg, "avg_hours": round(avg / 60, 2)}

    async def get_cases_created_by_day(self, days: int = 30) -> list[dict[str, Any]]:
        """Casos creados por día en los últimos N días."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            text("""
                SELECT
                    DATE(created_at) AS day,
                    COUNT(*) AS count
                FROM cases
                WHERE created_at >= :cutoff
                GROUP BY DATE(created_at)
                ORDER BY day ASC
            """),
            {"cutoff": cutoff},
        )
        rows = result.fetchall()
        return [{"date": str(r[0]), "count": r[1]} for r in rows]

    async def get_dashboard_summary(self) -> dict[str, Any]:
        """Resumen ejecutivo para el dashboard principal.

        Incluye contadores calculados a partir de cases + case_statuses + sla_records.
        Los cálculos que requieren subqueries (SLA en riesgo, backlog estancado,
        reapertura) viven en la misma consulta para minimizar round-trips.

        - solved_cases: Resueltos ∪ Cerrados ∪ Archivados (sin doble conteo).
        - at_risk_sla: SLAs entre 75% y 100% del target, no breached, no pausados,
          de casos activos y no finales.
        - stale_backlog: casos activos sin actualizar en >7 días.
        - reopened_cases / total_closed_ever / reopen_rate_pct: casos que alguna
          vez fueron cerrados (closed_at IS NOT NULL) y hoy están activos.
        """
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE c.is_archived = false) AS open_cases,
                COUNT(*) FILTER (WHERE DATE(c.created_at) = CURRENT_DATE) AS created_today,
                COUNT(*) FILTER (WHERE DATE(c.closed_at) = CURRENT_DATE) AS resolved_today,
                COUNT(*) FILTER (WHERE c.is_archived = false AND c.assigned_to IS NULL) AS unassigned,
                COUNT(*) FILTER (WHERE c.is_archived = true OR cs.slug IN ('resolved','closed')) AS solved_cases,
                (
                    SELECT COUNT(*)
                    FROM sla_records sr
                    JOIN cases cc ON cc.id = sr.case_id
                    JOIN case_statuses css ON css.id = cc.status_id
                    WHERE sr.is_breached = false
                      AND sr.paused_at IS NULL
                      AND sr.status_paused_at IS NULL
                      AND cc.is_archived = false
                      AND css.is_final = false
                      AND NOW() < sr.target_at
                      AND EXTRACT(EPOCH FROM (NOW() - sr.started_at))
                          >= 0.75 * EXTRACT(EPOCH FROM (sr.target_at - sr.started_at))
                ) AS at_risk_sla,
                (
                    SELECT COUNT(*)
                    FROM cases
                    WHERE is_archived = false
                      AND updated_at < NOW() - INTERVAL '7 days'
                ) AS stale_backlog,
                COUNT(*) FILTER (
                    WHERE c.closed_at IS NOT NULL
                      AND c.is_archived = false
                      AND cs.is_final = false
                ) AS reopened_cases,
                COUNT(*) FILTER (WHERE c.closed_at IS NOT NULL) AS total_closed_ever
            FROM cases c
            JOIN case_statuses cs ON cs.id = c.status_id
        """))
        row = result.fetchone()
        reopened = row[7] or 0
        total_closed_ever = row[8] or 0
        reopen_rate = round((reopened / total_closed_ever * 100), 2) if total_closed_ever > 0 else 0.0
        return {
            "open_cases": row[0] or 0,
            "created_today": row[1] or 0,
            "resolved_today": row[2] or 0,
            "unassigned": row[3] or 0,
            "solved_cases": row[4] or 0,
            "at_risk_sla": row[5] or 0,
            "stale_backlog": row[6] or 0,
            "reopened_cases": reopened,
            "total_closed_ever": total_closed_ever,
            "reopen_rate_pct": reopen_rate,
        }

    async def get_cases_by_level(self) -> list[dict[str, Any]]:
        """Distribución de casos activos por nivel actual (N0/N1/N2…)."""
        result = await self.db.execute(text("""
            SELECT c.current_level AS level, COUNT(c.id) AS count
            FROM cases c
            JOIN case_statuses cs ON cs.id = c.status_id
            WHERE c.is_archived = false
              AND cs.is_final = false
            GROUP BY c.current_level
            ORDER BY c.current_level ASC
        """))
        rows = result.fetchall()
        return [{"level": r[0], "count": r[1]} for r in rows]
