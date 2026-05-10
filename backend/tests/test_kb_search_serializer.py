"""
Tests for case_refs field in KB article serialization.

Strategy: test _serialize_article directly with MagicMock objects.

The conftest.py session fixture `_register_all_models` imports `backend.src.main`,
registering all models. We rely on that to make the module import chain work.
All three tests call _serialize_article (a pure Python function with no DB or
HTTP dependencies) using mock article objects, which mirrors the pattern of
test_kb_logic.py and test_kb_case_associations.py.
"""
from unittest.mock import MagicMock
from datetime import datetime, timezone


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_article(cases=None):
    """Build a MagicMock that looks like a KBArticleModel with optional linked cases."""
    now = datetime.now(timezone.utc)
    article = MagicMock()
    article.id = "art-001"
    article.title = "Test Article"
    article.content_json = {}
    article.content_text = "Test content"
    article.status = "draft"
    article.version = 1
    article.created_by_id = "user-001"
    article.approved_by_id = None
    article.published_at = None
    article.view_count = 0
    article.helpful_count = 0
    article.not_helpful_count = 0
    article.document_type_id = None
    article.visibility = "private"
    article.pending_visibility = None
    article.created_at = now
    article.updated_at = now
    # Relationships
    article.document_type = None
    article.tags = []
    article.created_by = None
    # kb_article_cases — list of KBArticleCaseModel mocks
    article.kb_article_cases = cases if cases is not None else []
    return article


def _make_case_link(case_number, case_title):
    """Build a MagicMock that looks like a KBArticleCaseModel with a case_ref."""
    link = MagicMock()
    case = MagicMock()
    case.case_number = case_number
    case.title = case_title
    link.case_ref = case
    return link


# ── tests ──────────────────────────────────────────────────────────────────────

def test_article_detail_includes_case_refs():
    """
    _serialize_article returns case_refs with case_number and case_title
    for each linked case.
    """
    from backend.src.modules.knowledge_base.router import _serialize_article

    link1 = _make_case_link("CASE-001", "Router is down")
    link2 = _make_case_link("CASE-002", "Email bounce issue")
    article = _make_article(cases=[link1, link2])

    result = _serialize_article(article)

    assert "case_refs" in result
    assert len(result["case_refs"]) == 2

    numbers = {ref["case_number"] for ref in result["case_refs"]}
    titles = {ref["case_title"] for ref in result["case_refs"]}
    assert "CASE-001" in numbers
    assert "CASE-002" in numbers
    assert "Router is down" in titles
    assert "Email bounce issue" in titles


def test_article_with_no_cases_returns_empty_list():
    """
    _serialize_article returns case_refs: [] when no cases are linked.
    """
    from backend.src.modules.knowledge_base.router import _serialize_article

    article = _make_article(cases=[])

    result = _serialize_article(article)

    assert "case_refs" in result
    assert result["case_refs"] == []


def test_article_list_includes_case_refs_per_item():
    """
    _serialize_article applied to multiple articles each produces a case_refs key.
    One article has linked cases; one has none.
    """
    from backend.src.modules.knowledge_base.router import _serialize_article

    link = _make_case_link("CASE-100", "VPN connectivity failure")
    article_with_cases = _make_article(cases=[link])
    article_with_cases.id = "art-with-cases"

    article_without = _make_article(cases=[])
    article_without.id = "art-no-cases"

    articles = [article_with_cases, article_without]
    results = [_serialize_article(a) for a in articles]

    # Every item must expose case_refs
    for r in results:
        assert "case_refs" in r, f"case_refs missing from article {r['id']}"

    # The linked article should have one entry
    with_cases = next(r for r in results if r["id"] == "art-with-cases")
    assert len(with_cases["case_refs"]) == 1
    assert with_cases["case_refs"][0]["case_number"] == "CASE-100"
    assert with_cases["case_refs"][0]["case_title"] == "VPN connectivity failure"

    # The unlinked article should have an empty list
    without = next(r for r in results if r["id"] == "art-no-cases")
    assert without["case_refs"] == []
