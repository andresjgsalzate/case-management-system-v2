import inspect


def test_list_articles_accepts_tag_slug_param():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    sig = inspect.signature(KBUseCases.list_articles)
    assert "tag_slug" in sig.parameters


def test_list_articles_tag_slug_default_is_none():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    sig = inspect.signature(KBUseCases.list_articles)
    assert sig.parameters["tag_slug"].default is None


def test_router_list_articles_exposes_tag_slug_query():
    from backend.src.modules.knowledge_base import router as kb_router
    src = inspect.getsource(kb_router.list_articles)
    assert "tag_slug" in src
