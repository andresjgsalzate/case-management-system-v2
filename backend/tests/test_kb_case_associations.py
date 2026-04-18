def test_kb_article_case_model_has_required_columns():
    from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel
    assert KBArticleCaseModel.__tablename__ == "kb_article_cases"
    cols = {c.name for c in KBArticleCaseModel.__table__.columns}
    assert cols == {"article_id", "case_id", "linked_at", "linked_by_id"}


def test_kb_article_case_model_has_composite_pk():
    from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel
    pk_cols = {c.name for c in KBArticleCaseModel.__table__.primary_key}
    assert pk_cols == {"article_id", "case_id"}


def test_kb_article_case_model_has_case_id_index():
    from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel
    indexed_col_names = set()
    for idx in KBArticleCaseModel.__table__.indexes:
        for col in idx.columns:
            indexed_col_names.add(col.name)
    assert "case_id" in indexed_col_names


def test_link_case_to_article_method_exists():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "link_case_to_article")


def test_link_case_to_article_signature():
    import inspect
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    sig = inspect.signature(KBUseCases.link_case_to_article)
    params = set(sig.parameters.keys())
    assert params == {"self", "article_id", "case_id", "user_id"}


def test_unlink_case_from_article_method_exists():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "unlink_case_from_article")


def test_unlink_case_from_article_signature():
    import inspect
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    sig = inspect.signature(KBUseCases.unlink_case_from_article)
    params = set(sig.parameters.keys())
    assert params == {"self", "article_id", "case_id"}


def test_list_article_cases_method_exists():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "list_article_cases")


def test_list_article_cases_signature():
    import inspect
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    sig = inspect.signature(KBUseCases.list_article_cases)
    params = set(sig.parameters.keys())
    assert params == {"self", "article_id", "can_access_cases"}


def test_list_case_articles_method_exists():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "list_case_articles")


def test_list_case_articles_signature():
    import inspect
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    sig = inspect.signature(KBUseCases.list_case_articles)
    params = set(sig.parameters.keys())
    assert params == {"self", "case_id"}


def test_router_has_article_cases_endpoints():
    from backend.src.modules.knowledge_base import router as kb_router
    paths = [getattr(r, "path", "") for r in kb_router.router.routes]
    methods_by_path: dict[str, set[str]] = {}
    for r in kb_router.router.routes:
        p = getattr(r, "path", "")
        ms = getattr(r, "methods", set()) or set()
        methods_by_path.setdefault(p, set()).update(ms)
    assert "/api/v1/kb/articles/{article_id}/cases" in paths
    assert "GET" in methods_by_path["/api/v1/kb/articles/{article_id}/cases"]
    assert "POST" in methods_by_path["/api/v1/kb/articles/{article_id}/cases"]
    assert "/api/v1/kb/articles/{article_id}/cases/{case_id}" in paths
    assert "DELETE" in methods_by_path["/api/v1/kb/articles/{article_id}/cases/{case_id}"]
