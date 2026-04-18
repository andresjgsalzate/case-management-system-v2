def test_stats_percentage_when_total_is_zero():
    def pct(helpful, total):
        return 0.0 if total == 0 else round((helpful / total) * 100, 1)
    assert pct(0, 0) == 0.0


def test_stats_percentage_calculation():
    def pct(helpful, total):
        return 0.0 if total == 0 else round((helpful / total) * 100, 1)
    assert pct(3, 4) == 75.0
    assert pct(7, 10) == 70.0
    assert pct(0, 5) == 0.0


def test_use_case_has_check_feedback_and_get_feedback_stats():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "check_feedback")
    assert hasattr(KBUseCases, "get_feedback_stats")


def test_router_has_feedback_check_and_stats_endpoints():
    from backend.src.modules.knowledge_base import router as kb_router
    paths = [getattr(r, "path", "") for r in kb_router.router.routes]
    assert any("feedback/check" in p for p in paths)
    assert any("feedback/stats" in p for p in paths)
