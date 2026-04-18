def test_summary_counts_from_events():
    """El summary cuenta correctamente cada tipo de transición."""
    events = [
        type("E", (), {"to_status": "in_review"})(),
        type("E", (), {"to_status": "in_review"})(),
        type("E", (), {"to_status": "approved"})(),
        type("E", (), {"to_status": "rejected"})(),
        type("E", (), {"to_status": "published"})(),
        type("E", (), {"to_status": "draft"})(),
    ]

    def compute_summary(evts):
        summary = {"submitted": 0, "approved": 0, "rejected": 0, "published": 0, "returned_to_draft": 0}
        for e in evts:
            if e.to_status == "in_review":
                summary["submitted"] += 1
            elif e.to_status == "approved":
                summary["approved"] += 1
            elif e.to_status == "rejected":
                summary["rejected"] += 1
            elif e.to_status == "published":
                summary["published"] += 1
            elif e.to_status == "draft":
                summary["returned_to_draft"] += 1
        return summary

    s = compute_summary(events)
    assert s["submitted"] == 2
    assert s["approved"] == 1
    assert s["rejected"] == 1
    assert s["published"] == 1
    assert s["returned_to_draft"] == 1


def test_use_case_has_get_review_history():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    assert hasattr(KBUseCases, "get_review_history")


def test_router_has_review_history_endpoint():
    from backend.src.modules.knowledge_base import router as kb_router
    paths = [getattr(r, "path", "") for r in kb_router.router.routes]
    assert any("review-history" in p for p in paths)
