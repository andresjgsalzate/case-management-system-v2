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

    async def get_sla_compliance_rate(self) -> dict[str, Any]:
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_breached = true) AS breached,
                COUNT(*) FILTER (WHERE is_breached = false) AS met
            FROM sla_records
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
        return [{"day": str(r[0]), "count": r[1]} for r in rows]

    async def get_dashboard_summary(self) -> dict[str, Any]:
        """Resumen ejecutivo para el dashboard principal."""
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE is_archived = false) AS open_cases,
                COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) AS created_today,
                COUNT(*) FILTER (WHERE DATE(closed_at) = CURRENT_DATE) AS resolved_today,
                COUNT(*) FILTER (WHERE is_archived = false AND assigned_to IS NULL) AS unassigned
            FROM cases
        """))
        row = result.fetchone()
        return {
            "open_cases": row[0] or 0,
            "created_today": row[1] or 0,
            "resolved_today": row[2] or 0,
            "unassigned": row[3] or 0,
        }
