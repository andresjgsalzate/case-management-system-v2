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
