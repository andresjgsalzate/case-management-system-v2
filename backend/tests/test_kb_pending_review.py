import inspect


def test_use_case_has_list_pending_review():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "list_pending_review")


def test_use_case_list_pending_review_is_coroutine():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert inspect.iscoroutinefunction(KBUseCases.list_pending_review)


def test_router_has_pending_review_endpoint():
    from backend.src.modules.knowledge_base import router as kb_router
    paths = [getattr(r, "path", "") for r in kb_router.router.routes]
    assert "/api/v1/kb/articles/pending-review" in paths or any(
        "pending-review" in p for p in paths
    )
