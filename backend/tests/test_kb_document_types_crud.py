import inspect


def test_use_case_has_document_type_crud_methods():
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    for name in (
        "list_document_types",
        "create_document_type",
        "update_document_type",
        "delete_document_type",
    ):
        assert hasattr(KBUseCases, name), f"Missing use case method: {name}"


def test_router_has_document_types_endpoints():
    from backend.src.modules.knowledge_base import router as kb_router
    methods_by_path: dict[str, set[str]] = {}
    for r in kb_router.router.routes:
        p = getattr(r, "path", "")
        if "document-types" in p:
            methods_by_path.setdefault(p, set()).update(getattr(r, "methods", set()))
    # Must have GET+POST on /document-types and PATCH+DELETE on /document-types/{id}
    list_path = next(p for p in methods_by_path if p.endswith("/document-types"))
    detail_path = next(p for p in methods_by_path if "{document_type_id}" in p)
    assert "GET" in methods_by_path[list_path]
    assert "POST" in methods_by_path[list_path]
    assert "PATCH" in methods_by_path[detail_path]
    assert "DELETE" in methods_by_path[detail_path]


def test_delete_is_soft_delete():
    """delete_document_type debe marcar is_active=False, no eliminar fila."""
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    src = inspect.getsource(KBUseCases.delete_document_type)
    assert "is_active" in src
    # No debe usar db.delete() en soft delete
    assert "self.db.delete" not in src
