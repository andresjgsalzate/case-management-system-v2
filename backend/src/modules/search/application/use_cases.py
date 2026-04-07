import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import ValidationError


def sanitize_tsquery(query: str) -> str:
    """
    Convierte texto libre en una tsquery válida de PostgreSQL.
    Elimina los operadores especiales de tsquery para evitar inyección.
    Habilita prefix matching con :* en cada término.

    Ejemplo: "error de red" → "error:* & de:* & red:*"
    """
    # Eliminar caracteres especiales que tienen significado en tsquery
    cleaned = re.sub(r"[&|!():*'\\]", " ", query)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    if not words:
        return ""
    return " & ".join(f"{w}:*" for w in words)


class SearchUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_all(
        self, query: str, limit: int = 10
    ) -> dict[str, list[dict[str, Any]]]:
        if not query.strip():
            raise ValidationError("El query no puede estar vacío")

        tsquery = sanitize_tsquery(query)
        if not tsquery:
            raise ValidationError("El query no puede estar vacío")

        cases = await self._search_cases(tsquery, limit)
        notes = await self._search_notes(tsquery, limit)
        kb = await self._search_kb(tsquery, limit)

        return {"cases": cases, "notes": notes, "kb_articles": kb}

    async def _search_cases(self, tsquery: str, limit: int) -> list[dict[str, Any]]:
        try:
            result = await self.db.execute(
                text("""
                    SELECT
                        c.id,
                        c.case_number,
                        c.title,
                        LEFT(c.description, 200) AS excerpt,
                        cs.name AS status,
                        c.created_at,
                        ts_rank(
                            to_tsvector('spanish',
                                COALESCE(c.case_number, '') || ' ' ||
                                COALESCE(c.title, '') || ' ' ||
                                COALESCE(c.description, '')
                            ),
                            to_tsquery('spanish', :tsquery)
                        ) AS rank
                    FROM cases c
                    JOIN case_statuses cs ON cs.id = c.status_id
                    WHERE c.is_archived = false
                      AND to_tsvector('spanish',
                            COALESCE(c.case_number, '') || ' ' ||
                            COALESCE(c.title, '') || ' ' ||
                            COALESCE(c.description, '')
                          ) @@ to_tsquery('spanish', :tsquery)
                    ORDER BY rank DESC
                    LIMIT :limit
                """),
                {"tsquery": tsquery, "limit": limit},
            )
            rows = result.fetchall()
            return [
                {
                    "type": "case",
                    "id": r[0],
                    "case_number": r[1],
                    "title": r[2],
                    "excerpt": r[3],
                    "status": r[4],
                    "created_at": str(r[5]),
                    "rank": float(r[6]),
                }
                for r in rows
            ]
        except Exception:
            return []

    async def _search_notes(self, tsquery: str, limit: int) -> list[dict[str, Any]]:
        try:
            result = await self.db.execute(
                text("""
                    SELECT
                        n.id,
                        n.case_id,
                        LEFT(n.content, 200) AS excerpt,
                        n.created_at,
                        u.full_name AS author,
                        ts_rank(
                            to_tsvector('spanish', COALESCE(n.content, '')),
                            to_tsquery('spanish', :tsquery)
                        ) AS rank
                    FROM case_notes n
                    LEFT JOIN users u ON u.id = n.user_id
                    WHERE n.is_deleted = false
                      AND to_tsvector('spanish', COALESCE(n.content, ''))
                          @@ to_tsquery('spanish', :tsquery)
                    ORDER BY rank DESC
                    LIMIT :limit
                """),
                {"tsquery": tsquery, "limit": limit},
            )
            rows = result.fetchall()
            return [
                {
                    "type": "note",
                    "id": r[0],
                    "case_id": r[1],
                    "excerpt": r[2],
                    "created_at": str(r[3]),
                    "author": r[4],
                    "rank": float(r[5]),
                }
                for r in rows
            ]
        except Exception:
            return []

    async def _search_kb(self, tsquery: str, limit: int) -> list[dict[str, Any]]:
        """Búsqueda en KB — la tabla kb_articles se crea en Fase 6; tolera su ausencia."""
        try:
            result = await self.db.execute(
                text("""
                    SELECT
                        a.id,
                        a.title,
                        LEFT(a.content_text, 200) AS excerpt,
                        a.created_at,
                        ts_rank(
                            to_tsvector('spanish',
                                COALESCE(a.title, '') || ' ' || COALESCE(a.content_text, '')
                            ),
                            to_tsquery('spanish', :tsquery)
                        ) AS rank
                    FROM kb_articles a
                    WHERE a.status = 'published'
                      AND to_tsvector('spanish',
                            COALESCE(a.title, '') || ' ' || COALESCE(a.content_text, '')
                          ) @@ to_tsquery('spanish', :tsquery)
                    ORDER BY rank DESC
                    LIMIT :limit
                """),
                {"tsquery": tsquery, "limit": limit},
            )
            rows = result.fetchall()
            return [
                {
                    "type": "kb_article",
                    "id": r[0],
                    "title": r[1],
                    "excerpt": r[2],
                    "created_at": str(r[3]),
                    "rank": float(r[4]),
                }
                for r in rows
            ]
        except Exception:
            # La tabla kb_articles no existe hasta Fase 6
            return []
