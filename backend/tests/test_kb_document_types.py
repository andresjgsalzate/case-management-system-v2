def test_document_type_model_has_required_fields():
    from backend.src.modules.knowledge_base.infrastructure.models import KBDocumentTypeModel
    model = KBDocumentTypeModel
    cols = {c.name for c in model.__table__.columns}
    assert {"id", "code", "name", "icon", "color", "is_active", "sort_order",
            "created_at", "updated_at"} <= cols


def test_article_has_document_type_id_column():
    from backend.src.modules.knowledge_base.infrastructure.models import KBArticleModel
    cols = {c.name for c in KBArticleModel.__table__.columns}
    assert "document_type_id" in cols


def test_article_has_document_type_relationship():
    from backend.src.modules.knowledge_base.infrastructure.models import KBArticleModel
    assert "document_type" in KBArticleModel.__mapper__.relationships
